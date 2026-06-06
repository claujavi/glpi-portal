"""
auth.py — Autenticación Active Directory (LDAP) + JWT
"""
from __future__ import annotations

import ssl
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request
from jose import JWTError, jwt
from ldap3 import ALL, SIMPLE, Connection, Server, Tls

from config import (
    AD_BASE_DN,
    AD_PORT,
    AD_SERVER,
    AD_UPN_SUFFIX,
    AD_USER_OU,
    JWT_EXPIRE_HOURS,
    JWT_SECRET,
)

# SSL sin verificación de certificado (igual que verify=False en httpx)
_tls = Tls(validate=ssl.CERT_NONE)
_FILTER_USUARIO = "(sAMAccountName={username})"


def autenticar_ad(username: str, password: str) -> dict:
    """
    Autentica contra AD con las credenciales del usuario.
    Devuelve dict con username, nombre, email.
    Lanza ValueError si las credenciales son incorrectas o el usuario está deshabilitado.
    """
    server = Server(AD_SERVER, port=AD_PORT, use_ssl=True, tls=_tls, get_info=ALL)

    # Bind UPN: usuario@vialidad.gob.ar
    conn = Connection(
        server,
        user=f"{username}@{AD_UPN_SUFFIX}",
        password=password,
        authentication=SIMPLE,
        auto_bind=False,
    )

    if not conn.bind():
        raise ValueError("Usuario o contraseña incorrectos")

    # Buscar atributos del usuario usando su propia sesión
    conn.search(
        AD_BASE_DN,
        _FILTER_USUARIO.format(username=username),
        attributes=["sAMAccountName", "displayName", "mail"],
    )

    if not conn.entries:
        conn.unbind()
        raise ValueError("Usuario no encontrado o inhabilitado")

    entry = conn.entries[0]
    usuario = {
        "username": str(entry.sAMAccountName),
        "nombre": str(entry.displayName) if entry.displayName else username,
        "email": str(entry.mail) if entry.mail else "",
    }
    conn.unbind()
    return usuario


def crear_token(usuario: dict) -> str:
    payload = {
        **usuario,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verificar_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except JWTError:
        raise ValueError("Token inválido o expirado")


def get_usuario_actual(request: Request) -> dict:
    """FastAPI dependency — extrae el usuario autenticado del cookie JWT."""
    token = request.cookies.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        return verificar_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Sesión expirada")
