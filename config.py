# =============================================================
#  config.py  —  editá estos valores antes de correr cualquier script
# =============================================================

GLPI_URL    = "https://soporte10.vialidad.gob.ar"            # server de prueba
APP_TOKEN   = "KqYahqZCoAW836oVDaytaeadBRCqX4KS8TXou69l"   # App-Token del cliente API (soporte10)
USER_TOKEN  = "ebaDkqi0uEiiQRryZCTDZnsHrUXKoahD0EGXmMh4"   # Token de API del usuario (soporte10)
GLPI_VERSION = 10   # 9 = producción (soporte.vialidad.gob.ar), 10 = desarrollo (soporte10)

# Active Directory
AD_SERVER        = "vialidad.gob.ar"
AD_PORT          = 636
AD_BASE_DN       = "DC=vialidad,DC=gob,DC=ar"
AD_USER_OU       = "OU=DNV Users,DC=vialidad,DC=gob,DC=ar"
AD_UPN_SUFFIX    = "vialidad.gob.ar"   # para bind UPN: usuario@vialidad.gob.ar

# JWT — cambiá JWT_SECRET por un string aleatorio largo antes de producción
JWT_SECRET       = "cambiar-esto-por-un-secreto-largo-y-aleatorio-en-produccion"
JWT_EXPIRE_HOURS = 8
