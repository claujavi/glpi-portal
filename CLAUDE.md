# CLAUDE.md — Contexto del proyecto glpi-portal

Este archivo le da contexto a Claude sobre el proyecto para continuar
el trabajo desde VS Code sin perder historia.

---

## Qué es este proyecto

Portal web amigable sobre GLPI 9 para usuarios finales (áreas de negocio).
El problema a resolver: GLPI manda mails técnicos que los usuarios no entienden,
y no tienen una forma amigable de seguir el estado de sus pedidos de desarrollo.

### Flujo actual (problemático)
1. Un área pide un desarrollo por nota vía GDE
2. Se crea un ticket en GLPI manualmente
3. GLPI manda mails automáticos poco amigables
4. El usuario no entiende qué está pasando con su pedido

### Flujo objetivo (con el portal)
1. Igual — el ticket se sigue cargando en GLPI
2. El usuario entra al portal con su usuario de Active Directory
3. Ve solo sus tickets en una interfaz tipo mensajería
4. Puede ver el estado, comentarios, adjuntos, y aprobar/rechazar avances
5. El portal escribe en GLPI vía API (seguimientos, adjuntos)

---

## Stack decidido

| Capa | Tecnología | Por qué |
|------|-----------|---------|
| Backend | FastAPI + Python | Ya lo usan en otros proyectos internos |
| Frontend | Jinja2 + HTMX | Ya lo usan, evita complejidad de React/Vue |
| HTTP client | httpx | Async nativo, mejor que requests |
| Auth AD | ldap3 | Mantenida activamente, python-ldap está muerta |
| Sesiones | JWT (python-jose) | Sin estado en el servidor |
| Infra | Docker en Proxmox | Tienen Proxmox + Linux + Windows disponibles |

---

## Infraestructura disponible

- Proxmox (host principal)
- Linux disponible
- Docker/contenedores
- Windows Server
- Active Directory on-premise para autenticación de usuarios

---

## GLPI

- **Versión**: 9.x
- **URL**: `https://soporte.vialidad.gob.ar`
- **API REST**: `https://soporte.vialidad.gob.ar/apirest.php`
- **Autenticación API**: App-Token (api key) + usuario/contraseña GLPI
- **Credenciales**: en `config.py` (excluido de git)

### Endpoints clave de GLPI 9
```
POST /apirest.php/initSession          → obtener session_token
GET  /apirest.php/killSession          → cerrar sesión
GET  /apirest.php/Ticket               → listar tickets
GET  /apirest.php/Ticket/{id}          → detalle de ticket
GET  /apirest.php/Ticket/{id}/ITILFollowup  → seguimientos (comentarios)
POST /apirest.php/ITILFollowup         → agregar seguimiento
GET  /apirest.php/Ticket/{id}/Document_Item → adjuntos
```

### Estados de tickets en GLPI 9
```python
ESTADOS = {
    1: "Nuevo",
    2: "En curso (asignado)",
    3: "En curso (planificado)",
    4: "Pendiente",
    5: "Resuelto",
    6: "Cerrado",
}
```

---

## Estructura del proyecto

```
glpi-portal/
├── CLAUDE.md               ← este archivo
├── README.md
├── config.py               ← credenciales reales, en .gitignore
├── config.example.py       ← template sin credenciales, en git
├── pyproject.toml          ← dependencias (uv)
├── uv.lock
├── .gitignore              ← incluye config.py y .venv/
│
├── 01_test_conexion.py     ← valida conectividad y auth con GLPI
├── 02_explorar_tickets.py  ← lista tickets y muestra seguimientos
├── 03_test_escritura.py    ← prueba agregar seguimiento a un ticket
│
├── glpi_client.py          ← cliente async GLPI (context manager, Pydantic)
├── main.py                 ← app FastAPI con rutas
├── templates/
│   ├── base.html           ← layout base con HTMX
│   ├── tickets.html        ← lista de tickets
│   ├── ticket.html         ← detalle + conversación
│   ├── error.html          ← página de error genérica
│   └── partials/
│       └── seguimientos.html  ← fragmento HTMX para la conversación
└── static/
    └── style.css           ← estilos (sin framework externo)
```

---

## Estado actual

- [x] Arquitectura diseñada
- [x] Scripts de validación creados (01, 02, 03)
- [x] Repositorio GitHub creado y sincronizado
- [x] uv configurado con dependencias (fastapi, httpx, urllib3, jinja2, uvicorn)
- [x] `glpi_client.py` — cliente async con Pydantic (Ticket, Seguimiento, Adjunto)
- [x] `main.py` — app FastAPI con rutas (lista + detalle + agregar seguimiento)
- [x] Templates Jinja2 + HTMX (lista, detalle, conversación en tiempo real)
- [x] CSS propio sin framework externo
- [ ] **Bloqueado**: App-Token de GLPI incorrecto — esperando credenciales del admin
- [ ] Validar scripts 01, 02, 03 cuando el token esté corregido
- [ ] Autenticación LDAP con AD on-premise (auth.py)
- [ ] Filtrar tickets por usuario autenticado
- [ ] Deploy en Docker/Proxmox

---

## Convenciones del proyecto

- **Siempre usar `uv run`** para correr scripts, no `python` directo
- **Nunca commitear `config.py`** — está en `.gitignore`
- **httpx** para todo HTTP, no requests
- **Pydantic v2** para modelar datos de la API de GLPI
- Código en **español** para variables de dominio (ticket, seguimiento, estado)
- Código en **inglés** para infraestructura (client, router, handler)

---

## Comandos frecuentes

```bash
# Correr scripts de validación
uv run 01_test_conexion.py
uv run 02_explorar_tickets.py
uv run 03_test_escritura.py

# Agregar dependencia
uv add nombre-paquete

# Sincronizar entorno (después de clonar)
uv sync

# Correr la app FastAPI (cuando esté lista)
uv run fastapi dev main.py
```

---

## Notas importantes

- GLPI 9 y GLPI 10 tienen APIs diferentes — este proyecto es específico para v9
- El `verify=False` en httpx es intencional: el certificado SSL puede ser self-signed
- Los seguimientos con `is_private=0` los ve el solicitante; con `1` solo los técnicos
- La autenticación del portal usa AD (ldap3), distinto al usuario GLPI de la API
- El usuario GLPI de `config.py` es solo para que la API funcione, no es el usuario final
