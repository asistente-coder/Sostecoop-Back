"""Bitácora del admin. Usa base temporal: DATABASE_URL=sqlite:///./test_tmp.db python test_activity.py"""

from fastapi.testclient import TestClient

from app.main import app

CRED = {"email": "admin@cooperativa.com", "password": "CambiaEsta123"}

with TestClient(app, headers={"Origin": "http://localhost:3000"}) as c:
    assert c.get("/api/admin/activity").status_code == 401  # solo con sesión

    # intento fallido: queda registrado sin sesión y sin la contraseña
    assert c.post("/api/admin/login", json={**CRED, "password": "mal-secreto"}).status_code == 401
    assert c.post("/api/admin/login", json=CRED).status_code == 200
    page = c.get("/api/admin/activity").json()
    acciones = [i["action"] for i in page["items"]]
    assert acciones[:2] == ["login", "login_failed"], acciones
    fallido = page["items"][1]
    assert fallido["admin_email"] is None and fallido["details"] == {"email": CRED["email"]}, fallido
    assert "mal-secreto" not in str(page)
    assert page["items"][0]["admin_email"] == CRED["email"] and page["items"][0]["ip"]

    antes = c.get("/api/admin/activity").json()["total"]

    # editar: antes/después en title y solo nombres de campo en content
    sec = c.get("/api/admin/sections").json()
    hero = next(s for s in sec if s["key"] == "hero")
    nuevo = {**hero["content"], "title": "OTRO TITULO"}
    r = c.put("/api/admin/sections/hero", json={"title": "Hero nuevo", "content": nuevo})
    assert r.status_code == 200
    last = c.get("/api/admin/activity?limit=1").json()["items"][0]
    assert last["action"] == "section_update" and last["entity_type"] == "section" and last["entity_key"] == "hero"
    assert last["details"]["title"] == {"before": hero["title"], "after": "Hero nuevo"}
    assert last["details"]["content_fields"] == ["title"], last["details"]
    assert "hero" in last["summary"] and "contenido (title)" in last["summary"]

    # guardar lo mismo no registra nada
    total = c.get("/api/admin/activity").json()["total"]
    c.put("/api/admin/sections/hero", json={"title": "Hero nuevo", "content": nuevo})
    assert c.get("/api/admin/activity").json()["total"] == total

    # un rechazo (403) tampoco deja registro
    assert c.put("/api/admin/sections/hero", json={"visible": False}).status_code == 403
    assert c.delete("/api/admin/sections/hero").status_code == 403
    assert c.get("/api/admin/activity").json()["total"] == total

    # crear, borrar, subir
    body = {"key": "modulo-log", "title": "Modulo", "content": {"items": []}}
    assert c.post("/api/admin/sections", json=body).status_code == 201
    assert c.delete("/api/admin/sections/modulo-log").status_code == 204
    up = c.post("/api/admin/upload", files={"file": ("foto.png", b"\x89PNG", "image/png")}).json()
    items = c.get("/api/admin/activity?limit=3").json()["items"]
    assert [i["action"] for i in items] == ["upload", "section_delete", "section_create"], items
    assert items[0]["entity_key"] == up["url"] and items[0]["details"]["original_name"] == "foto.png"
    assert items[0]["details"]["bytes"] == 4

    # contactos: leer dos veces registra una sola vez
    c.post("/api/public/contact", json={"name": "Ana", "email": "ana@x.com", "message": "Hola, quiero info"})
    cid = c.get("/api/admin/contacts").json()[0]["id"]
    c.patch(f"/api/admin/contacts/{cid}/read")
    c.patch(f"/api/admin/contacts/{cid}/read")
    assert c.get(f"/api/admin/activity?action=contact_read&entity_key={cid}").json()["total"] == 1
    assert c.delete(f"/api/admin/contacts/{cid}").status_code == 204
    assert c.get("/api/admin/activity?action=contact_delete").json()["items"][0]["details"]["name"] == "Ana"

    # filtros y paginación
    assert c.get("/api/admin/activity?entity_type=section&entity_key=hero").json()["total"] == 1
    p1 = c.get("/api/admin/activity?limit=2&offset=0").json()
    p2 = c.get("/api/admin/activity?limit=2&offset=2").json()
    assert len(p1["items"]) == 2 and p1["total"] == p2["total"]
    assert {i["id"] for i in p1["items"]}.isdisjoint({i["id"] for i in p2["items"]})
    assert c.get("/api/admin/activity?limit=0").status_code == 422
    assert c.get("/api/admin/activity?limit=500").status_code == 422
    ids = [i["id"] for i in c.get("/api/admin/activity?limit=200").json()["items"]]
    assert ids == sorted(ids, reverse=True)  # más reciente primero

    # logout
    assert c.post("/api/admin/logout").status_code == 204
    assert c.get("/api/admin/activity").status_code == 401
    c.post("/api/admin/login", json=CRED)
    assert c.get("/api/admin/activity?action=logout").json()["total"] == 1
print("ACTIVIDAD OK")
