"""Prueba rápida: python -m pytest no hace falta, se ejecuta con `python test_smoke.py`."""

from fastapi.testclient import TestClient

from app.main import app

with TestClient(app) as c:
    c.headers["Origin"] = "http://localhost:3000"  # el navegador lo envía solo; la sesión va en la cookie
    pub = c.get("/api/public/content").json()
    assert len(pub) == 9, pub

    assert c.get("/api/admin/sections").status_code == 401
    assert c.post("/api/admin/login", json={"email": "admin@cooperativa.com", "password": "mal"}).status_code == 401
    r = c.post("/api/admin/login", json={"email": "admin@cooperativa.com", "password": "CambiaEsta123"})
    assert r.status_code == 200 and "sostecoop_admin" in c.cookies
    h = {}

    with c.websocket_connect("/api/public/ws") as ws:
        r = c.put("/api/admin/sections/hero", headers=h, json={"content": {"title": "NUEVO TITULO"}})
        assert r.status_code == 200
        msg = ws.receive_json()
        assert msg["event"] == "section_updated" and msg["data"]["content"]["title"] == "NUEVO TITULO"

    c.put("/api/admin/sections/faq", headers=h, json={"visible": False})
    assert len(c.get("/api/public/content").json()) == 8
    assert len(c.get("/api/admin/sections", headers=h).json()) == 9
    c.put("/api/admin/sections/faq", headers=h, json={"visible": True})

    r = c.post("/api/public/contact", json={"name": "Ana", "email": "ana@x.com", "message": "Hola, quiero info"})
    assert r.status_code == 201
    assert c.post("/api/public/contact", json={"name": "A", "email": "no", "message": "x"}).status_code == 422
    lst = c.get("/api/admin/contacts", headers=h).json()
    assert lst and not lst[0]["read"]
    assert c.patch(f"/api/admin/contacts/{lst[0]['id']}/read", headers=h).json()["read"]

    up = c.post("/api/admin/upload", headers=h, files={"file": ("a.png", b"\x89PNG", "image/png")})
    assert up.status_code == 200 and c.get(up.json()["url"]).status_code == 200
    assert (
        c.post("/api/admin/upload", headers=h, files={"file": ("a.exe", b"x", "application/x-msdownload")}).status_code
        == 400
    )
print("TODO OK")
