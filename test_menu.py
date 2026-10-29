"""Límite del menú. Usa base temporal: DATABASE_URL=sqlite:///./test_tmp.db python test_menu.py"""

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.menu import MAX_MENU_ITEMS

assert MAX_MENU_ITEMS == 10


def menu(n):
    return [{"label": f"Enlace {i}", "anchor": f"#enlace-{i}"} for i in range(1, n + 1)]


with TestClient(app, headers={"Origin": "http://localhost:3000"}) as c:
    body = {"content": {"site_name": "X", "menu": menu(3)}}
    assert c.put("/api/admin/sections/settings", json=body).status_code == 401  # solo con sesión

    login = {"email": settings.admin_email, "password": settings.admin_password}
    assert c.post("/api/admin/login", json=login).status_code == 200

    def saved_menu():
        sec = next(s for s in c.get("/api/admin/sections").json() if s["key"] == "settings")
        return sec["content"]["menu"]

    # hasta 10 enlaces se aceptan, incluido el límite exacto
    for n in (0, 1, 9, 10):
        r = c.put("/api/admin/sections/settings", json={"content": {"site_name": "X", "menu": menu(n)}})
        assert r.status_code == 200, (n, r.text)
        assert len(r.json()["content"]["menu"]) == n
    assert len(saved_menu()) == 10

    with c.websocket_connect("/api/public/ws") as ws:
        # 11 o más se rechazan con un mensaje claro
        for n in (11, 25):
            r = c.put("/api/admin/sections/settings", json={"content": {"site_name": "X", "menu": menu(n)}})
            assert r.status_code == 422, (n, r.status_code)
            detail = r.json()["detail"]
            assert "máximo 10" in detail and f"se enviaron {n}" in detail, detail
        # lo rechazado no se guarda ni se anuncia a los visitantes
        assert saved_menu() == menu(10)
        ok = c.put("/api/admin/sections/settings", json={"title": "Ajustes", "content": {"menu": menu(2)}})
        assert ok.status_code == 200
        assert ws.receive_json()["data"]["content"]["menu"] == menu(2)  # el primer evento es el guardado válido

    # el menú debe ser una lista
    for malo in ("texto", {"a": 1}, 5):
        r = c.put("/api/admin/sections/settings", json={"content": {"menu": malo}})
        assert r.status_code == 422 and "lista" in r.json()["detail"], (malo, r.text)

    # sin «menu» en el contenido no hay nada que validar, y la regla es solo de settings
    assert c.put("/api/admin/sections/settings", json={"content": {"site_name": "Sin menu"}}).status_code == 200
    assert c.put("/api/admin/sections/settings", json={"visible": True}).status_code == 200
    hero = next(s for s in c.get("/api/admin/sections").json() if s["key"] == "hero")
    assert c.put("/api/admin/sections/hero", json={"content": {**hero["content"], "menu": menu(15)}}).status_code == 200

    # un rechazo no deja rastro en la bitácora
    antes = c.get("/api/admin/activity").json()["total"]
    c.put("/api/admin/sections/settings", json={"content": {"menu": menu(11)}})
    assert c.get("/api/admin/activity").json()["total"] == antes
print("MENU OK")
