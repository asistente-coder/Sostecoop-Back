"""Sesión por cookie, CSRF y CORS. Usa base temporal: DATABASE_URL=sqlite:///./test_tmp.db python test_cookie.py"""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.security import create_token

OK = "http://localhost:3000"
CRED = {"email": settings.admin_email, "password": settings.admin_password}


def new_client():
    return TestClient(app, headers={"Origin": OK})


with TestClient(app) as boot:  # arranca la app (crea tablas y admin)
    pass

# --- login: la cookie lleva el JWT y el cuerpo no ---
c = new_client()
r = c.post("/api/admin/login", json=CRED)
assert r.status_code == 200 and r.json() == {"email": CRED["email"]}, r.text
assert "access_token" not in r.text
sc = r.headers["set-cookie"].lower()
assert sc.startswith("sostecoop_admin=") and "httponly" in sc and "samesite=lax" in sc and "path=/" in sc, sc
assert f"max-age={settings.token_minutes * 60}" in sc and "secure" not in sc, sc

# producción: Secure
settings.environment = "production"
try:
    assert "secure" in new_client().post("/api/admin/login", json=CRED).headers["set-cookie"].lower()
finally:
    settings.environment = "development"

# --- /me ---
assert c.get("/api/admin/me").json() == {"email": CRED["email"]}
assert new_client().get("/api/admin/me").status_code == 401
bad = new_client()
bad.cookies.set("sostecoop_admin", "basura")
assert bad.get("/api/admin/me").status_code == 401
old = jwt.encode(
    {"sub": CRED["email"], "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
    settings.secret_key,
    algorithm="HS256",
)
exp = new_client()
exp.cookies.set("sostecoop_admin", old)
assert exp.get("/api/admin/me").status_code == 401
# el header Authorization ya no sirve
assert (
    new_client().get("/api/admin/me", headers={"Authorization": f"Bearer {create_token(CRED['email'])}"}).status_code
    == 401
)

# --- CSRF: solo en solicitudes que cambian datos ---
body = {"content": {"title": "CSRF"}}
assert c.put("/api/admin/sections/hero", json=body, headers={"Origin": "http://evil.com"}).status_code == 403
assert c.post("/api/admin/logout", headers={"Origin": "null"}).status_code == 403
sin_origen = TestClient(app, cookies=c.cookies)  # sin Origin ni Referer
assert sin_origen.put("/api/admin/sections/hero", json=body).status_code == 403
assert sin_origen.put("/api/admin/sections/hero", json=body, headers={"Referer": OK + "/admin"}).status_code == 200
assert (
    sin_origen.put("/api/admin/sections/hero", json=body, headers={"Referer": "http://evil.com/x"}).status_code == 403
)
assert (
    sin_origen.put("/api/admin/sections/hero", json=body, headers={"Origin": "http://testserver"}).status_code == 200
)  # mismo host (/admin)
assert c.put("/api/admin/sections/hero", json=body).status_code == 200  # origen listado
assert (
    c.get("/api/admin/sections", headers={"Origin": "http://evil.com"}).status_code == 200
)  # lectura: la bloquea CORS

# --- CORS con credenciales ---
pre = {"Access-Control-Request-Method": "PUT", "Access-Control-Request-Headers": "content-type"}
r = c.options("/api/admin/sections/hero", headers={**pre, "Origin": OK})
assert r.headers["access-control-allow-origin"] == OK and r.headers["access-control-allow-credentials"] == "true"
for origen in ("http://evil.com", "http://192.168.12.200:3000"):
    r = c.options("/api/admin/sections/hero", headers={**pre, "Origin": origen})
    assert "access-control-allow-origin" not in r.headers, origen
r = c.get("/api/public/content", headers={"Origin": OK})
assert r.headers["access-control-allow-origin"] == OK and r.headers["access-control-allow-credentials"] == "true"

# --- logout: borra la cookie con los mismos atributos ---
r = c.post("/api/admin/logout")
assert r.status_code == 204
sc = r.headers["set-cookie"].lower()
assert (
    sc.startswith("sostecoop_admin=")
    and "max-age=0" in sc
    and "path=/" in sc
    and "httponly" in sc
    and "samesite=lax" in sc
), sc
assert c.get("/api/admin/me").status_code == 401
print("COOKIE OK")
