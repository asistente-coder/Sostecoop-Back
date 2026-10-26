"""Crear/borrar módulos. Usa base temporal: DATABASE_URL=sqlite:///./test_tmp.db python test_sections.py"""
from fastapi.testclient import TestClient

from app.main import app

with TestClient(app) as c:
    body = {"key": "ahorro-escolar", "title": "Ahorro escolar", "visible": True, "position": 9,
            "content": {"template": "preguntas", "title": "Ahorro escolar", "items": []}}
    assert c.post("/api/admin/sections", json=body).status_code == 401
    tk = c.post("/api/admin/login", json={"email": "admin@cooperativa.com", "password": "CambiaEsta123"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tk}"}

    with c.websocket_connect("/api/public/ws") as ws:
        r = c.post("/api/admin/sections", headers=h, json=body)
        assert r.status_code == 201 and r.json()["key"] == "ahorro-escolar" and r.json()["position"] == 9, r.text
        m = ws.receive_json()
        assert m["event"] == "section_updated" and m["data"]["key"] == "ahorro-escolar"

        assert c.post("/api/admin/sections", headers=h, json=body).status_code == 409
        assert c.post("/api/admin/sections", headers=h, json={**body, "key": "Mal Formato"}).status_code == 422
        assert c.post("/api/admin/sections", headers=h, json={**body, "key": "a"}).status_code == 422
        for k in ["inicio", "admin", "hero"]:
            assert c.post("/api/admin/sections", headers=h, json={**body, "key": k}).status_code == 422, k
        auto = c.post("/api/admin/sections", headers=h, json={"key": "otro", "title": "Otro"}).json()
        assert auto["position"] == 10 and auto["content"] == {}, auto
        assert ws.receive_json()["data"]["key"] == "otro"

        assert c.delete("/api/admin/sections/ahorro-escolar", headers=h).status_code == 204
        assert ws.receive_json() == {"event": "section_deleted", "data": {"key": "ahorro-escolar"}}
        assert c.delete("/api/admin/sections/ahorro-escolar", headers=h).status_code == 404
        for k in ["settings", "hero", "nosotros", "noticias", "contacto"]:
            assert c.delete(f"/api/admin/sections/{k}", headers=h).status_code == 403, k
        assert c.delete("/api/admin/sections/otro", headers=h).status_code == 204
        assert c.delete("/api/admin/sections/faq", headers=h).status_code == 204  # sí se puede
print("MODULOS OK")
