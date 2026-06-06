# Scripts de validación GLPI 9

Tres scripts para probar la API REST de GLPI antes de construir el portal.

## Setup (una sola vez)

```bash
# Con uv (recomendado)
uv init
uv add httpx

# O con pip
pip install httpx
```

## Configuración

Editá `config.py` con tus datos reales:

```python
GLPI_URL  = "http://tu-servidor/glpi"   # URL de tu GLPI
APP_TOKEN = "TU_API_KEY_AQUI"           # la api key que te pasaron
GLPI_USER = "admin"                     # usuario local de GLPI (no AD)
GLPI_PASS = "tu_password"
```

> La API key se configura en GLPI en:
> **Configuración → General → API → Token de aplicación**
> Si no está habilitada la API REST, activarla en esa misma pantalla.

## Orden de ejecución

### 1. Probar conexión
```bash
python 01_test_conexion.py
```
Prueba HTTP y HTTPS automáticamente. Si funciona, te dice qué URL usar en `config.py`.

### 2. Explorar tickets
```bash
python 02_explorar_tickets.py
```
Lista los últimos 5 tickets y permite ver el detalle de uno:
seguimientos, adjuntos, y estructura raw de los campos.

### 3. Probar escritura
```bash
python 03_test_escritura.py
```
Agrega un comentario de prueba a un ticket. Usá un ticket de prueba,
no uno de producción. Confirma antes de escribir.

## Qué validar en cada paso

| Script | Qué confirma |
|--------|-------------|
| 01 | La API está habilitada y la api_key es válida |
| 02 | Podemos leer tickets y seguimientos (lo que verá el usuario en el portal) |
| 03 | Podemos escribir seguimientos (para cuando el usuario apruebe/rechace desde el portal) |

## Si el script 01 falla

- Verificar que la API REST esté activa: GLPI → Configuración → General → API
- Verificar que el App-Token esté habilitado para la URL del servidor
- Si hay certificado SSL self-signed, los scripts ya lo manejan (verify=False)
- Si GLPI está detrás de un proxy o subpath, ajustar GLPI_URL

## Próximo paso

Una vez que los 3 scripts funcionan, arrancar con el portal:
- `FastAPI` para el backend
- `Jinja2 + HTMX` para el frontend  
- `ldap3` para autenticación con AD on-premise
