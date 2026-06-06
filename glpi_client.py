"""
glpi_client.py — Cliente async para GLPI 9 REST API
"""
from __future__ import annotations

import html
import re
from typing import Optional

import httpx
from pydantic import BaseModel

from config import APP_TOKEN, GLPI_URL, USER_TOKEN

ESTADOS = {
    1: "Nuevo",
    2: "En curso (asignado)",
    3: "En curso (planificado)",
    4: "Pendiente",
    5: "Resuelto",
    6: "Cerrado",
}

PRIORIDADES = {
    1: "Muy baja",
    2: "Baja",
    3: "Media",
    4: "Alta",
    5: "Muy alta",
    6: "Mayor",
}

# CSS class por estado, para los badges del frontend
ESTADO_CSS = {
    1: "nuevo",
    2: "en-curso",
    3: "en-curso",
    4: "pendiente",
    5: "resuelto",
    6: "cerrado",
}


def _limpiar_html(texto: str) -> str:
    texto = html.unescape(texto)
    texto = re.sub(r"<br\s*/?>", "\n", texto)
    texto = re.sub(r"<[^>]+>", "", texto)
    return texto.strip()


class Ticket(BaseModel):
    id: int
    name: str = "Sin título"
    status: int = 1
    date: Optional[str] = None
    date_mod: Optional[str] = None
    priority: int = 3
    content: Optional[str] = None
    users_id_recipient: Optional[int | str] = None

    @property
    def estado(self) -> str:
        return ESTADOS.get(self.status, f"Estado {self.status}")

    @property
    def estado_css(self) -> str:
        return ESTADO_CSS.get(self.status, "")

    @property
    def prioridad(self) -> str:
        return PRIORIDADES.get(self.priority, "?")

    @property
    def descripcion(self) -> str:
        return _limpiar_html(self.content) if self.content else ""

    @property
    def fecha(self) -> str:
        return self.date[:10] if self.date else ""


class Seguimiento(BaseModel):
    id: int
    date: Optional[str] = None
    users_id: int | str | None = None
    content: str = ""
    is_private: int = 0

    @property
    def texto(self) -> str:
        return _limpiar_html(self.content)

    @property
    def es_privado(self) -> bool:
        return bool(self.is_private)

    @property
    def fecha(self) -> str:
        return self.date[:16].replace("T", " ") if self.date else ""


class Adjunto(BaseModel):
    id: int
    name: Optional[str] = None
    filename: Optional[str] = None
    mime: Optional[str] = None

    @property
    def nombre_archivo(self) -> str:
        return self.filename or self.name or f"adjunto_{self.id}"


class GLPIClient:
    """
    Context manager async para la API REST de GLPI 9.

    Uso:
        async with GLPIClient() as client:
            tickets = await client.listar_tickets()
    """

    def __init__(self):
        self._base = GLPI_URL.rstrip("/")
        self._headers = {
            "App-Token": APP_TOKEN,
            "Content-Type": "application/json",
        }
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> GLPIClient:
        self._http = httpx.AsyncClient(verify=False, timeout=15)
        await self._iniciar_sesion()
        return self

    async def __aexit__(self, *_):
        await self._cerrar_sesion()
        if self._http:
            await self._http.aclose()

    async def _iniciar_sesion(self):
        resp = await self._http.get(
            f"{self._base}/apirest.php/initSession",
            headers={**self._headers, "Authorization": f"user_token {USER_TOKEN}"},
        )
        resp.raise_for_status()
        self._headers["Session-Token"] = resp.json()["session_token"]

    async def _cerrar_sesion(self):
        if "Session-Token" not in self._headers:
            return
        try:
            await self._http.get(
                f"{self._base}/apirest.php/killSession",
                headers=self._headers,
            )
        except Exception:
            pass

    async def _get(self, endpoint: str, params: dict | None = None) -> dict | list:
        resp = await self._http.get(
            f"{self._base}/apirest.php/{endpoint}",
            headers=self._headers,
            params=params or {},
        )
        if resp.status_code == 206:  # partial content = lista paginada
            return resp.json()
        resp.raise_for_status()
        return resp.json()

    async def listar_tickets(
        self,
        cantidad: int = 20,
        usuario_id: int | None = None,
    ) -> list[Ticket]:
        params: dict = {
            "range": f"0-{cantidad - 1}",
            "sort": "id",
            "order": "DESC",
            "expand_dropdowns": True,
        }
        if usuario_id:
            params["searchText[users_id_recipient]"] = usuario_id
        data = await self._get("Ticket", params)
        if isinstance(data, list):
            return [Ticket.model_validate(t) for t in data]
        return []

    async def obtener_ticket(self, ticket_id: int) -> Ticket:
        data = await self._get(f"Ticket/{ticket_id}", {"expand_dropdowns": True})
        return Ticket.model_validate(data)

    async def obtener_seguimientos(self, ticket_id: int) -> list[Seguimiento]:
        try:
            data = await self._get(f"Ticket/{ticket_id}/ITILFollowup")
            if isinstance(data, list):
                return [Seguimiento.model_validate(s) for s in data]
        except httpx.HTTPStatusError:
            pass
        return []

    async def agregar_seguimiento(
        self,
        ticket_id: int,
        contenido: str,
        privado: bool = False,
    ) -> bool:
        payload = {
            "input": {
                "items_id": ticket_id,
                "itemtype": "Ticket",
                "content": contenido,
                "is_private": int(privado),
            }
        }
        resp = await self._http.post(
            f"{self._base}/apirest.php/ITILFollowup",
            headers=self._headers,
            json=payload,
        )
        return resp.status_code in (200, 201)

    async def obtener_adjuntos(self, ticket_id: int) -> list[Adjunto]:
        try:
            data = await self._get(f"Ticket/{ticket_id}/Document_Item")
            if isinstance(data, list):
                return [Adjunto.model_validate(a) for a in data]
        except httpx.HTTPStatusError:
            pass
        return []
