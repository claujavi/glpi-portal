"""
Script 1 — Verificar conectividad y autenticación
--------------------------------------------------
Qué hace:
  1. Prueba HTTP y HTTPS automáticamente
  2. Inicia sesión con app_token + user/pass
  3. Muestra el session_token si todo va bien
  4. Cierra la sesión correctamente

Cómo correr:
  uv run 01_test_conexion.py
  (o: python 01_test_conexion.py)
"""

import httpx
import sys
from config import GLPI_URL, APP_TOKEN, USER_TOKEN


def probar_url(base_url: str) -> str | None:
    """Intenta conectarse a GLPI con user_token + App-Token y devuelve el session_token, o None."""
    url = f"{base_url}/apirest.php/initSession"
    headers = {
        "Authorization": f"user_token {USER_TOKEN}",
        "App-Token": APP_TOKEN,
        "Content-Type": "application/json",
    }

    print(f"\n→ Probando: {url}")
    try:
        resp = httpx.get(url, headers=headers, timeout=10, verify=False)
        print(f"  Status: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            if "session_token" in data:
                print(f"  ✓ Sesión iniciada correctamente")
                print(f"  session_token: {data['session_token'][:20]}...")
                return data["session_token"]
            else:
                print(f"  ✗ Respuesta inesperada: {data}")
        else:
            print(f"  ✗ Error: {resp.text[:200]}")

    except httpx.ConnectError as e:
        print(f"  ✗ No se pudo conectar: {e}")
    except httpx.TimeoutException:
        print(f"  ✗ Timeout")
    except Exception as e:
        print(f"  ✗ Error inesperado: {type(e).__name__}: {e}")

    return None


def cerrar_sesion(base_url: str, session_token: str):
    url = f"{base_url}/apirest.php/killSession"
    headers = {
        "App-Token": APP_TOKEN,
        "Session-Token": session_token,
    }
    try:
        resp = httpx.get(url, headers=headers, timeout=10, verify=False)
        if resp.status_code == 200:
            print("\n  ✓ Sesión cerrada correctamente")
        else:
            print(f"\n  ⚠ No se pudo cerrar sesión: {resp.status_code}")
    except Exception as e:
        print(f"\n  ⚠ Error al cerrar sesión: {e}")


def main():
    print("=" * 55)
    print("  GLPI — Test de conexión y autenticación")
    print("=" * 55)

    # Probar la URL tal como está en config.py
    urls_a_probar = [GLPI_URL]

    # Si empieza con http://, probar también la versión https:// y viceversa
    if GLPI_URL.startswith("http://"):
        urls_a_probar.append(GLPI_URL.replace("http://", "https://", 1))
    elif GLPI_URL.startswith("https://"):
        urls_a_probar.append(GLPI_URL.replace("https://", "http://", 1))

    session_token = None
    url_ok = None

    for base_url in urls_a_probar:
        token = probar_url(base_url)
        if token:
            session_token = token
            url_ok = base_url
            break

    print("\n" + "=" * 55)
    if session_token:
        print(f"  ✓ URL que funciona: {url_ok}")
        print(f"  → Actualizá GLPI_URL en config.py con este valor")
        cerrar_sesion(url_ok, session_token)
    else:
        print("  ✗ No se pudo conectar con ninguna URL")
        print("\n  Revisá:")
        print("  - Que GLPI_URL apunte al servidor correcto")
        print("  - Que APP_TOKEN sea válido (Configuración > API en GLPI)")
        print("  - Que GLPI_USER y GLPI_PASS sean correctos")
        print("  - Que la API REST esté habilitada en GLPI")
        print("    (Configuración > General > API > Activar API REST)")
        sys.exit(1)


if __name__ == "__main__":
    # Suprimir warnings de SSL para certificados self-signed internos
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
