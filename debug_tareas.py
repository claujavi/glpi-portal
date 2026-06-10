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

        # Document_Item del ticket directamente
        url0 = f"{BASE}/apirest.php/Ticket/{TICKET_ID}/Document_Item"
        resp0 = await http.get(url0, headers=HEADERS)
        print(f"GET {url0} -> {resp0.status_code}")
        print(f"  {resp0.text[:500]}\n")

        # Obtener tareas
        url = f"{BASE}/apirest.php/Ticket/{TICKET_ID}/TicketTask"
        resp = await http.get(url, headers=HEADERS)
        print(f"GET {url} -> {resp.status_code}")
        tareas = resp.json() if resp.status_code == 200 else []
        for t in tareas:
            print(f"  Tarea id={t['id']} state={t['state']}")

        # Verificar Document_Item de cada tarea y el documento en si
        for t in tareas:
            url2 = f"{BASE}/apirest.php/TicketTask/{t['id']}/Document_Item"
            resp2 = await http.get(url2, headers=HEADERS)
            print(f"\n  GET {url2} -> {resp2.status_code}")
            items = resp2.json() if resp2.status_code == 200 else []
            for item in items:
                doc_id = item.get("documents_id")
                print(f"  Document_Item id={item['id']} documents_id={doc_id}")
                url3 = f"{BASE}/apirest.php/Document/{doc_id}"
                resp3 = await http.get(url3, headers=HEADERS)
                print(f"    GET {url3} -> {resp3.status_code}")
                print(f"    {resp3.text[:300]}")

        await http.get(f"{BASE}/apirest.php/killSession", headers=HEADERS)


asyncio.run(main())
