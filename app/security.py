import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

from urllib.parse import urlparse

import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import Admin

COOKIE_NAME = "sostecoop_admin"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _cookie_options() -> dict:
    # Los mismos atributos al crear y al borrar la cookie, si no el navegador no la reconoce como la misma
    return {"path": "/", "httponly": True, "samesite": "lax", "secure": settings.cookie_secure}


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(COOKIE_NAME, token, max_age=settings.token_minutes * 60, **_cookie_options())


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, **_cookie_options())


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return salt.hex() + "$" + digest.hex()


def verify_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 200_000)
    return hmac.compare_digest(digest.hex(), digest_hex)


def create_token(email: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.token_minutes)
    return jwt.encode({"sub": email, "exp": exp}, settings.secret_key, algorithm="HS256")


def decode_token(token: str) -> str | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"]).get("sub")
    except jwt.PyJWTError:
        return None


def current_admin(request: Request, db: Session = Depends(get_db)) -> Admin:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    email = decode_token(token)
    admin = db.query(Admin).filter(Admin.email == email).first() if email else None
    if not admin:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida o expirada")
    return admin


def csrf_protect(request: Request) -> None:
    """Las solicitudes que cambian datos solo se aceptan si vienen de un origen autorizado.

    Los navegadores envían siempre `Origin` en POST/PUT/PATCH/DELETE (o `Referer` como respaldo);
    una página de otro sitio no puede falsearlo.
    """
    if request.method in SAFE_METHODS:
        return
    origin = request.headers.get("origin")
    if not origin or origin == "null":
        referer = request.headers.get("referer")
        if referer:
            parts = urlparse(referer)
            origin = f"{parts.scheme}://{parts.netloc}"
    if not origin or origin == "null":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Falta el origen de la solicitud")
    same_site = urlparse(origin).netloc == request.headers.get("host")  # el propio panel /admin
    if not (same_site or origin.rstrip("/") in settings.origins):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Origen no permitido")
