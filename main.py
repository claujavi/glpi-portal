"""
main.py — Portal GLPI: app FastAPI principal
"""
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx

from auth import autenticar_ad, crear_token, get_usuario_actual
from glpi_client import GLPIClient

app = FastAPI(title="Portal de Pedidos")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def _build_timeline(seguimientos, adjuntos, tareas=None) -> list[dict]:
    items = (
        [{"tipo": "seguimiento", "item": s} for s in seguimientos]
        + [{"tipo": "adjunto", "item": a} for a in adjuntos]
        + [{"tipo": "tarea", "item": t} for t in (tareas or [])]
    )
    return sorted(items, key=lambda x: (
        x["item"].date_creation if x["tipo"] == "adjunto" else (x["item"].date or "")
    ))


@app.exception_handler(401)
async def auth_exception_handler(request: Request, exc: HTTPException):
    return RedirectResponse(url="/login")


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    if request.cookies.get("token"):
        return RedirectResponse(url="/tickets")
    return templates.TemplateResponse(request=request, name="login.html", context={})


@app.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    try:
        usuario = autenticar_ad(username, password)
    except ValueError as e:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": str(e), "username_previo": username},
        )

    token = crear_token(usuario)
    response = RedirectResponse(url="/tickets", status_code=303)
    response.set_cookie(
        key="token", value=token, httponly=True, samesite="lax", max_age=60 * 60 * 8
    )
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("token")
    return response


# ── Tickets ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=RedirectResponse)
async def root():
    return RedirectResponse(url="/tickets")


@app.get("/tickets", response_class=HTMLResponse)
async def lista_tickets(
    request: Request,
    q: str = "",
    usuario: dict = Depends(get_usuario_actual),
):
    try:
        async with GLPIClient() as client:
            todos = await client.listar_tickets(cantidad=50)
    except (httpx.HTTPStatusError, httpx.ConnectError, Exception) as exc:
        mensaje = (
            f"Error HTTP {exc.response.status_code}" if isinstance(exc, httpx.HTTPStatusError)
            else str(exc)
        )
        return templates.TemplateResponse(
            request=request, name="error.html",
            context={"mensaje": mensaje, "usuario": usuario},
        )

    # Filtrar por usuario logueado
    tickets = [
        t for t in todos
        if str(t.users_id_recipient).lower() == usuario["username"].lower()
    ]

    # Filtrar por búsqueda (título o #ID)
    if q:
        q_lower = q.lower().strip()
        q_id = q_lower.lstrip("#")
        tickets = [
            t for t in tickets
            if q_lower in t.name.lower()
            or (q_id.isdigit() and str(t.id) == q_id)
        ]

    # HTMX pide solo el fragmento de la lista
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request=request,
            name="partials/ticket_list.html",
            context={"tickets": tickets},
        )

    return templates.TemplateResponse(
        request=request,
        name="tickets.html",
        context={"tickets": tickets, "usuario": usuario, "q": q},
    )


@app.get("/tickets/{ticket_id}", response_class=HTMLResponse)
async def detalle_ticket(
    request: Request,
    ticket_id: int,
    usuario: dict = Depends(get_usuario_actual),
):
    try:
        async with GLPIClient() as client:
            ticket = await client.obtener_ticket(ticket_id)
            seguimientos = await client.obtener_seguimientos(ticket_id)
            tareas = await client.obtener_tareas(ticket_id)
            adjuntos = await client.obtener_adjuntos(ticket_id, followup_ids=[s.id for s in seguimientos], tarea_ids=[t.id for t in tareas])
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Ticket no encontrado")

    timeline = _build_timeline(seguimientos, adjuntos, tareas)
    return templates.TemplateResponse(
        request=request,
        name="ticket.html",
        context={
            "ticket": ticket,
            "timeline": timeline,
            "usuario": usuario,
        },
    )


@app.post("/tickets/{ticket_id}/seguimiento", response_class=HTMLResponse)
async def agregar_seguimiento(
    request: Request,
    ticket_id: int,
    contenido: str = Form(...),
    usuario: dict = Depends(get_usuario_actual),
):
    async with GLPIClient() as client:
        await client.agregar_seguimiento(ticket_id, contenido)
        seguimientos = await client.obtener_seguimientos(ticket_id)
        tareas = await client.obtener_tareas(ticket_id)
        adjuntos = await client.obtener_adjuntos(ticket_id, followup_ids=[s.id for s in seguimientos], tarea_ids=[t.id for t in tareas])

    timeline = _build_timeline(seguimientos, adjuntos, tareas)
    return templates.TemplateResponse(
        request=request,
        name="partials/timeline.html",
        context={"timeline": timeline, "ticket_id": ticket_id},
    )



@app.get("/adjunto/{documents_id}")
async def descargar_adjunto(
    documents_id: int,
    usuario: dict = Depends(get_usuario_actual),
):
    async with GLPIClient() as client:
        content, filename, mime = await client.descargar_adjunto(documents_id)
    return Response(
        content=content,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/tickets/{ticket_id}/adjunto", response_class=HTMLResponse)
async def subir_adjunto(
    request: Request,
    ticket_id: int,
    archivo: UploadFile = File(...),
    usuario: dict = Depends(get_usuario_actual),
):
    content = await archivo.read()
    async with GLPIClient() as client:
        await client.subir_adjunto(
            ticket_id,
            archivo.filename,
            content,
            archivo.content_type or "application/octet-stream",
        )

    # Recarga la página completa para que GLPI tenga tiempo de indexar el nuevo archivo
    return HTMLResponse(
        content="",
        headers={"HX-Redirect": f"/tickets/{ticket_id}"},
    )
