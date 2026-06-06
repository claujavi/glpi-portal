"""
Script 2 — Explorar tickets y seguimientos
-------------------------------------------
Qué hace:
  1. Lista los últimos 5 tickets del sistema
  2. Para cada ticket muestra: id, título, estado, asignado
  3. Pide un ID de ticket y muestra todos sus seguimientos (comentarios)
  4. Muestra los adjuntos del ticket si tiene

Cómo correr:
  uv run 02_explorar_tickets.py
  (o: python 02_explorar_tickets.py)
"""

import httpx
import json
from datetime import datetime
from config import GLPI_URL, APP_TOKEN, USER_TOKEN

# Suprimir warnings SSL
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Estados de GLPI 9 (los valores numéricos de la API)
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


class GLPIClient:
    def __init__(self):
        self.base = GLPI_URL.rstrip("/")
        self.headers = {
            "App-Token": APP_TOKEN,
            "Content-Type": "application/json",
        }
        self.session_token: str | None = None
        self.client = httpx.Client(verify=False, timeout=15)

    def iniciar_sesion(self):
        resp = self.client.get(
            f"{self.base}/apirest.php/initSession",
            headers={**self.headers, "Authorization": f"user_token {USER_TOKEN}"},
        )
        resp.raise_for_status()
        self.session_token = resp.json()["session_token"]
        self.headers["Session-Token"] = self.session_token
        print(f"✓ Sesión iniciada\n")

    def cerrar_sesion(self):
        if self.session_token:
            self.client.get(
                f"{self.base}/apirest.php/killSession",
                headers=self.headers,
            )
            print("\n✓ Sesión cerrada")

    def get(self, endpoint: str, params: dict = None) -> dict | list:
        resp = self.client.get(
            f"{self.base}/apirest.php/{endpoint}",
            headers=self.headers,
            params=params or {},
        )
        if resp.status_code == 206:  # partial content = lista paginada
            return resp.json()
        resp.raise_for_status()
        return resp.json()

    def listar_tickets(self, cantidad: int = 5) -> list:
        return self.get("Ticket", {
            "range": f"0-{cantidad - 1}",
            "sort": "id",
            "order": "DESC",
            "expand_dropdowns": True,
        })

    def obtener_ticket(self, ticket_id: int) -> dict:
        return self.get(f"Ticket/{ticket_id}", {"expand_dropdowns": True})

    def obtener_seguimientos(self, ticket_id: int) -> list:
        """Seguimientos = ITILFollowup = los comentarios/mensajes del ticket."""
        return self.get(f"Ticket/{ticket_id}/ITILFollowup")

    def obtener_adjuntos(self, ticket_id: int) -> list:
        """Documentos adjuntos al ticket."""
        try:
            return self.get(f"Ticket/{ticket_id}/Document_Item")
        except httpx.HTTPStatusError:
            return []


def formatear_fecha(fecha_str: str | None) -> str:
    if not fecha_str or fecha_str == "NULL":
        return "—"
    try:
        dt = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return fecha_str


def mostrar_tickets(tickets: list):
    print("=" * 65)
    print(f"  Últimos {len(tickets)} tickets")
    print("=" * 65)

    for t in tickets:
        estado = ESTADOS.get(t.get("status", 0), f"Estado {t.get('status')}")
        prioridad = PRIORIDADES.get(t.get("priority", 0), "?")
        print(f"\n  ID #{t['id']}  [{estado}]  — Prioridad: {prioridad}")
        print(f"  Título   : {t.get('name', 'Sin título')}")
        print(f"  Apertura : {formatear_fecha(t.get('date'))}")
        print(f"  Asignado : {t.get('users_id_assign') or '(sin asignar)'}")


def mostrar_seguimientos(seguimientos: list):
    if not seguimientos:
        print("\n  (sin seguimientos)")
        return

    print(f"\n  {len(seguimientos)} seguimiento(s):\n")
    for i, f in enumerate(seguimientos, 1):
        fecha = formatear_fecha(f.get("date"))
        usuario = f.get("users_id") or "Sistema"
        # El contenido viene con HTML en GLPI — limpieza básica
        contenido = f.get("content", "")
        contenido_limpio = contenido.replace("<br />", "\n  ").replace("<br>", "\n  ")
        # Truncar si es muy largo
        if len(contenido_limpio) > 300:
            contenido_limpio = contenido_limpio[:300] + "..."
        print(f"  ── Seguimiento {i} ──────────────────────────")
        print(f"  Fecha  : {fecha}")
        print(f"  Usuario: {usuario}")
        print(f"  Texto  :\n  {contenido_limpio}")


def mostrar_adjuntos(adjuntos: list):
    if not adjuntos:
        print("\n  (sin adjuntos)")
        return
    print(f"\n  {len(adjuntos)} adjunto(s):")
    for a in adjuntos:
        print(f"  - {a.get('filename') or a.get('name') or json.dumps(a)}")


def main():
    client = GLPIClient()

    try:
        client.iniciar_sesion()

        # Listar últimos tickets
        tickets = client.listar_tickets(5)
        mostrar_tickets(tickets)

        # Pedir ID de ticket para explorar en detalle
        print("\n" + "=" * 65)
        ticket_id_str = input("  Ingresá el ID de un ticket para ver detalle (Enter para saltar): ").strip()

        if ticket_id_str.isdigit():
            ticket_id = int(ticket_id_str)
            print(f"\n── Detalle del ticket #{ticket_id} ─────────────────────────")

            ticket = client.obtener_ticket(ticket_id)
            print(f"  Título      : {ticket.get('name')}")
            print(f"  Estado      : {ESTADOS.get(ticket.get('status', 0), '?')}")
            print(f"  Descripción :\n  {(ticket.get('content') or '').replace('<br />', chr(10)+'  ')[:400]}")

            print("\n── Seguimientos ─────────────────────────────────────────")
            seguimientos = client.obtener_seguimientos(ticket_id)
            mostrar_seguimientos(seguimientos)

            print("\n── Adjuntos ─────────────────────────────────────────────")
            adjuntos = client.obtener_adjuntos(ticket_id)
            mostrar_adjuntos(adjuntos)

        # Mostrar estructura raw de un ticket para entender el modelo
        print("\n" + "=" * 65)
        print("  Estructura raw del primer ticket (para entender los campos):")
        print("=" * 65)
        if tickets:
            print(json.dumps(tickets[0], indent=2, ensure_ascii=False)[:1500])
            print("  ... (truncado)")

    except httpx.HTTPStatusError as e:
        print(f"\n✗ Error HTTP {e.response.status_code}: {e.response.text[:300]}")
    except Exception as e:
        print(f"\n✗ Error: {type(e).__name__}: {e}")
    finally:
        client.cerrar_sesion()


if __name__ == "__main__":
    main()
