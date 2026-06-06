"""
Script 3 — Probar escritura: agregar un seguimiento a un ticket
---------------------------------------------------------------
Qué hace:
  1. Agrega un comentario de prueba a un ticket existente
  2. Verifica que el seguimiento se creó correctamente
  3. Muestra el ID del seguimiento creado

⚠ ATENCIÓN: esto modifica un ticket real en GLPI.
  Usá un ticket de prueba, no uno de producción.

Cómo correr:
  uv run 03_test_escritura.py
  (o: python 03_test_escritura.py)
"""

import httpx
import json
from config import GLPI_URL, APP_TOKEN, GLPI_USER, GLPI_PASS

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class GLPIClient:
    def __init__(self):
        self.base = GLPI_URL.rstrip("/")
        self.headers = {
            "App-Token": APP_TOKEN,
            "Content-Type": "application/json",
        }
        self.client = httpx.Client(verify=False, timeout=15)

    def iniciar_sesion(self):
        resp = self.client.get(
            f"{self.base}/apirest.php/initSession",
            headers=self.headers,
            auth=(GLPI_USER, GLPI_PASS),
        )
        resp.raise_for_status()
        self.headers["Session-Token"] = resp.json()["session_token"]
        print("✓ Sesión iniciada\n")

    def cerrar_sesion(self):
        self.client.get(f"{self.base}/apirest.php/killSession", headers=self.headers)
        print("\n✓ Sesión cerrada")

    def agregar_seguimiento(self, ticket_id: int, mensaje: str, privado: bool = False) -> dict:
        """
        Agrega un seguimiento (comentario) a un ticket.
        privado=True → solo lo ven los técnicos, no el solicitante
        privado=False → lo ve el solicitante (lo que queremos para el portal)
        """
        payload = {
            "input": {
                "items_id": ticket_id,
                "itemtype": "Ticket",
                "content": mensaje,
                "is_private": 1 if privado else 0,
            }
        }
        resp = self.client.post(
            f"{self.base}/apirest.php/ITILFollowup",
            headers=self.headers,
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    def obtener_seguimientos(self, ticket_id: int) -> list:
        resp = self.client.get(
            f"{self.base}/apirest.php/Ticket/{ticket_id}/ITILFollowup",
            headers=self.headers,
        )
        if resp.status_code in (200, 206):
            return resp.json()
        return []


def main():
    client = GLPIClient()

    print("=" * 55)
    print("  GLPI — Test de escritura (agregar seguimiento)")
    print("=" * 55)

    ticket_id_str = input("\n  ID del ticket de prueba: ").strip()
    if not ticket_id_str.isdigit():
        print("  ✗ ID inválido")
        return

    ticket_id = int(ticket_id_str)

    print(f"\n  ⚠  Esto va a agregar un comentario al ticket #{ticket_id}")
    confirmar = input("  ¿Confirmás? (s/n): ").strip().lower()
    if confirmar != "s":
        print("  Cancelado")
        return

    try:
        client.iniciar_sesion()

        mensaje = (
            "✅ Prueba de integración desde portal externo.\n"
            "Este comentario fue generado automáticamente por el script de validación."
        )

        print(f"\n→ Agregando seguimiento al ticket #{ticket_id}...")
        resultado = client.agregar_seguimiento(ticket_id, mensaje, privado=False)

        print(f"\n✓ Seguimiento creado:")
        print(json.dumps(resultado, indent=2, ensure_ascii=False))

        # Verificar que aparece en la lista
        print(f"\n→ Verificando que el seguimiento existe...")
        seguimientos = client.obtener_seguimientos(ticket_id)
        print(f"  Total de seguimientos ahora: {len(seguimientos)}")

        if seguimientos:
            ultimo = seguimientos[-1]
            print(f"  Último seguimiento:")
            print(f"    ID      : {ultimo.get('id')}")
            print(f"    Fecha   : {ultimo.get('date')}")
            print(f"    Privado : {'Sí' if ultimo.get('is_private') else 'No'}")
            contenido = (ultimo.get('content') or '')[:150]
            print(f"    Texto   : {contenido}")

        print("\n✓ Escritura funciona correctamente — el portal puede agregar seguimientos")

    except httpx.HTTPStatusError as e:
        print(f"\n✗ Error HTTP {e.response.status_code}: {e.response.text[:400]}")

        if e.response.status_code == 400:
            print("\n  Posibles causas:")
            print("  - El usuario no tiene permiso para crear seguimientos")
            print("  - El perfil de API no tiene habilitado POST en ITILFollowup")

    except Exception as e:
        print(f"\n✗ Error: {type(e).__name__}: {e}")
    finally:
        client.cerrar_sesion()


if __name__ == "__main__":
    main()
