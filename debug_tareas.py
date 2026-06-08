"""
debug_tareas.py — verifica qué devuelve GLPI para TicketTask
"""
import asyncio
import httpx
from config import APP_TOKEN, GLPI_URL, USER_TOKEN

BASE = GLPI_URL.rstrip("/")
HEADERS = {"App-Token": APP_TOKEN, "Content-Type": "application/json"}

TICKET_ID = 53488


async def main():
    async with httpx.AsyncClient(verify=False, timeout=15) as http:
        resp = await http.get(
            f"{BASE}/apirest.php/initSession",
            headers={**HEADERS, "Authorization": f"user_token {USER_TOKEN}"},
        )
        resp.raise_for_status()
        HEADERS["Session-Token"] = resp.json()["session_token"]

        for endpoint in ["ITILTask", "TicketTask"]:
            url = f"{BASE}/apirest.php/Ticket/{TICKET_ID}/{endpoint}"
            print(f"\nGET {url}")
            resp = await http.get(url, headers=HEADERS)
            print(f"Status: {resp.status_code}")
            print(resp.text[:1000])

        await http.get(f"{BASE}/apirest.php/killSession", headers=HEADERS)


asyncio.run(main())
