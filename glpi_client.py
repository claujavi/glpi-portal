"""
glpi_client.py — Cliente async para GLPI 9 REST API
"""
from __future__ import annotations

import html
import re
from typing import Optional

import httpx
from pydantic import BaseModel

from config import APP_TOKEN, GLPI_URL, GLPI_VERSION, USER_TOKEN

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
    nombre_display: Optional[str] = None  # resuelto post-fetch

    @property
    def texto(self) -> str:
        return _limpiar_html(self.content)

    @property
    def es_privado(self) -> bool:
        return bool(self.is_private)

    @property
    def fecha(self) -> str:
        return self.date[:16].replace("T", " ") if self.date else ""

    @property
    def autor(self) -> str:
        return self.nombre_display or str(self.users_id or "Desconocido")


ESTADOS_TAREA = {
    0: "Información",
    1: "Por hacer",
    2: "Hecho",
}


class Tarea(BaseModel):
    id: int
    date: Optional[str] = None
    users_id: int | str | None = None
    content: str = ""
    state: int = 0
    is_private: int = 0
    nombre_display: Optional[str] = None

    @property
    def texto(self) -> str:
        return _limpiar_html(self.content)

    @property
    def es_privado(self) -> bool:
        return bool(self.is_private)

    @property
    def fecha(self) -> str:
        return self.date[:16].replace("T", " ") if self.date else ""

    @property
    def estado(self) -> str:
        return ESTADOS_TAREA.get(self.state, "")

    @property
    def autor(self) -> str:
        return self.nombre_display or str(self.users_id or "Desconocido")


class Adjunto(BaseModel):
    id: int                          # Document_Item ID
    documents_id: Optional[int] = None  # Document ID (para descargar)
    name: Optional[str] = None
    filename: Optional[str] = None
    mime: Optional[str] = None
    date_creation: Optional[str] = None  # viene del Document_Item

    @property
    def nombre_archivo(self) -> str:
        return self.filename or self.name or f"adjunto_{self.id}"

    @property
    def fecha(self) -> str:
        return self.date_creation[:16].replace("T", " ") if self.date_creation else ""


class GLPIClient:
    """
    Context manager async para la API REST de GLPI 9.

    Uso:
        async with GLPIClient() as client:
            tickets = await client.listar_tickets()
    """

    # Nombres de endpoints que cambiaron entre GLPI 9 y 10
    _TASK_ENDPOINT = "ITILTask" if GLPI_VERSION >= 10 else "TicketTask"

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

    async def _nombre_usuario(self, user_id: int) -> str:
        try:
            data = await self._get(f"User/{user_id}")
            firstname = (data.get("firstname") or "").strip()
            realname = (data.get("realname") or "").strip()
            nombre = f"{firstname} {realname}".strip()
            return nombre or data.get("name") or str(user_id)
        except httpx.HTTPStatusError:
            return str(user_id)

    async def obtener_seguimientos(self, ticket_id: int) -> list[Seguimiento]:
        try:
            data = await self._get(f"Ticket/{ticket_id}/ITILFollowup")
            if not isinstance(data, list):
                return []
            seguimientos = [Seguimiento.model_validate(s) for s in data]

            # Resolver nombres reales de usuarios únicos
            ids_unicos = {s.users_id for s in seguimientos if isinstance(s.users_id, int)}
            nombres = {}
            for uid in ids_unicos:
                nombres[uid] = await self._nombre_usuario(uid)
            for s in seguimientos:
                if isinstance(s.users_id, int) and s.users_id in nombres:
                    s.nombre_display = nombres[s.users_id]

            return seguimientos
        except httpx.HTTPStatusError:
            pass
        return []

    async def obtener_tareas(self, ticket_id: int) -> list[Tarea]:
        try:
            data = await self._get(f"Ticket/{ticket_id}/{self._TASK_ENDPOINT}")
            if not isinstance(data, list):
                return []
            tareas = [Tarea.model_validate(t) for t in data]

            ids_unicos = {t.users_id for t in tareas if isinstance(t.users_id, int)}
            nombres = {}
            for uid in ids_unicos:
                nombres[uid] = await self._nombre_usuario(uid)
            for t in tareas:
                if isinstance(t.users_id, int) and t.users_id in nombres:
                    t.nombre_display = nombres[t.users_id]

            return tareas
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

    async def crear_tarea(self, ticket_id: int, contenido: str) -> bool:
        payload = {
            "input": {
                "tickets_id": ticket_id,
                "content": contenido,
                "state": 1,
                "is_private": 0,
            }
        }
        resp = await self._http.post(
            f"{self._base}/apirest.php/{self._TASK_ENDPOINT}",
            headers=self._headers,
            json=payload,
        )
        return resp.status_code in (200, 201)

    async def aprobar_tarea(self, tarea_id: int) -> bool:
        payload = {"input": {"state": 2}}
        resp = await self._http.put(
            f"{self._base}/apirest.php/{self._TASK_ENDPOINT}/{tarea_id}",
            headers=self._headers,
            json=payload,
        )
        return resp.status_code in (200, 201)

    async def subir_adjunto(
        self,
        ticket_id: int,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> bool:
        import json as _json

        # GLPI 9 requiere que el nombre del campo en el form coincida
        # exactamente con el valor de _filename en el manifest
        field_name = "file"
        manifest = _json.dumps({"input": {"name": filename, "_filename": [field_name]}})
        headers_sin_content_type = {
            k: v for k, v in self._headers.items() if k != "Content-Type"
        }
        resp = await self._http.post(
            f"{self._base}/apirest.php/Document",
            headers=headers_sin_content_type,
            files={
                "uploadManifest": (None, manifest, "application/json"),
                field_name: (filename, content, content_type or "application/octet-stream"),
            },
        )
        if resp.status_code not in (200, 201):
            return False

        resp_data = resp.json()
        doc_id = resp_data.get("id") if isinstance(resp_data, dict) else None
        if not doc_id:
            return False

        payload = {
            "input": {
                "documents_id": doc_id,
                "itemtype": "Ticket",
                "items_id": ticket_id,
                "timeline_position": 1,  # TIMELINE_LEFT — necesario para mostrar en la timeline de GLPI
            }
        }
        resp2 = await self._http.post(
            f"{self._base}/apirest.php/Document_Item",
            headers=self._headers,
            json=payload,
        )
        return resp2.status_code in (200, 201)

    async def obtener_adjuntos(
        self,
        ticket_id: int,
        followup_ids: list[int] | None = None,
        tarea_ids: list[int] | None = None,
    ) -> list[Adjunto]:
        raw_items: list[dict] = []

        # Documentos vinculados directamente al ticket
        try:
            items = await self._get(f"Ticket/{ticket_id}/Document_Item")
            if isinstance(items, list):
                raw_items.extend(items)
        except httpx.HTTPStatusError:
            pass

        # Documentos vinculados a cada followup
        for fid in (followup_ids or []):
            try:
                items = await self._get(f"ITILFollowup/{fid}/Document_Item")
                if isinstance(items, list):
                    raw_items.extend(items)
            except httpx.HTTPStatusError:
                pass

        # Documentos vinculados a cada tarea
        for tid in (tarea_ids or []):
            try:
                items = await self._get(f"{self._TASK_ENDPOINT}/{tid}/Document_Item")
                if isinstance(items, list):
                    raw_items.extend(items)
            except httpx.HTTPStatusError:
                # GLPI 9 puede no soportar el sub-recurso; buscar directamente
                try:
                    items = await self._get("Document_Item", {
                        "searchText[itemtype]": self._TASK_ENDPOINT,
                        "searchText[items_id]": str(tid),
                    })
                    if isinstance(items, list):
                        raw_items.extend(items)
                except httpx.HTTPStatusError:
                    pass

        # Deduplicar por documents_id (un mismo archivo puede aparecer en varios niveles)
        seen: set[int] = set()
        adjuntos: list[Adjunto] = []
        for item in raw_items:
            doc_id = item.get("documents_id")
            if not doc_id or doc_id in seen:
                continue
            seen.add(doc_id)
            try:
                doc = await self._get(f"Document/{doc_id}")
                adjuntos.append(Adjunto(
                    id=item["id"],
                    documents_id=doc_id,
                    name=doc.get("name"),
                    filename=doc.get("filename"),
                    mime=doc.get("mime"),
                    date_creation=item.get("date_creation"),
                ))
            except httpx.HTTPStatusError:
                adjuntos.append(Adjunto(
                    id=item["id"],
                    documents_id=doc_id,
                    date_creation=item.get("date_creation"),
                ))
        return adjuntos

    async def eliminar_adjunto(self, item_id: int) -> bool:
        resp = await self._http.delete(
            f"{self._base}/apirest.php/Document_Item/{item_id}",
            headers=self._headers,
        )
        return resp.status_code in (200, 204)

    async def descargar_adjunto(self, documents_id: int) -> tuple[bytes, str, str]:
        resp = await self._http.get(
            f"{self._base}/apirest.php/Document/{documents_id}",
            headers=self._headers,
            params={"alt": "media"},
        )
        resp.raise_for_status()
        cd = resp.headers.get("Content-Disposition", "")
        filename = "adjunto"
        if 'filename="' in cd:
            filename = cd.split('filename="')[1].rstrip('"')
        elif "filename=" in cd:
            filename = cd.split("filename=")[1].split(";")[0].strip()
        mime = resp.headers.get("Content-Type", "application/octet-stream")
        return resp.content, filename, mime
