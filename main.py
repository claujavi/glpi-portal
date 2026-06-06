"""
main.py — Portal GLPI: app FastAPI principal
"""
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx

from glpi_client import GLPIClient

app = FastAPI(title="Portal de Pedidos")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/tickets")


@app.get("/tickets", response_class=HTMLResponse)
async def lista_tickets(request: Request):
    try:
        async with GLPIClient() as client:
            tickets = await client.listar_tickets()
    except (httpx.HTTPStatusError, httpx.ConnectError, Exception) as exc:
        mensaje = (
            f"Error HTTP {exc.response.status_code}" if isinstance(exc, httpx.HTTPStatusError)
            else str(exc)
        )
        return templates.TemplateResponse(
            "error.html", {"request": request, "mensaje": mensaje}
        )

    return templates.TemplateResponse(
        "tickets.html", {"request": request, "tickets": tickets}
    )


@app.get("/tickets/{ticket_id}", response_class=HTMLResponse)
async def detalle_ticket(request: Request, ticket_id: int):
    try:
        async with GLPIClient() as client:
            ticket = await client.obtener_ticket(ticket_id)
            seguimientos = await client.obtener_seguimientos(ticket_id)
            adjuntos = await client.obtener_adjuntos(ticket_id)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Ticket no encontrado")

    return templates.TemplateResponse(
        "ticket.html",
        {
            "request": request,
            "ticket": ticket,
            "seguimientos": seguimientos,
            "adjuntos": adjuntos,
        },
    )


@app.post("/tickets/{ticket_id}/seguimiento", response_class=HTMLResponse)
async def agregar_seguimiento(
    request: Request,
    ticket_id: int,
    contenido: str = Form(...),
):
    async with GLPIClient() as client:
        await client.agregar_seguimiento(ticket_id, contenido)
        seguimientos = await client.obtener_seguimientos(ticket_id)

    # HTMX espera solo el fragmento — no la página completa
    return templates.TemplateResponse(
        "partials/seguimientos.html",
        {"request": request, "seguimientos": seguimientos},
    )
