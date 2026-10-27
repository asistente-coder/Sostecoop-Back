"""Secciones obligatorias. Usa base temporal: DATABASE_URL=sqlite:///./test_tmp.db python test_required.py"""
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Section
from app.seed import REQUIRED_KEYS, seed

assert REQUIRED_KEYS == {"hero", "nosotros", "noticias", "settings", "contacto"}


def public_keys(c):
    return [s["key"] for s in c.get("/api/public/content").json()]


with TestClient(app) as c:
    c.headers["Origin"] = "http://localhost:3000"
    assert c.post("/api/admin/login", json={"email": "admin@cooperativa.com", "password": "CambiaEsta123"}).status_code == 200
    h = {}  # la sesión va en la cookie

    for k in REQUIRED_KEYS:
        # no se puede ocultar ni borrar
        assert c.put(f"/api/admin/sections/{k}", headers=h, json={"visible": False}).status_code == 403, k
        assert c.put(f"/api/admin/sections/{k}", headers=h, json={"visible": False, "title": "X"}).status_code == 403, k
        assert c.delete(f"/api/admin/sections/{k}", headers=h).status_code == 403, k
        # sí se puede editar título y contenido, y dejarla visible
        r = c.put(f"/api/admin/sections/{k}", headers=h, json={"visible": True, "title": f"Titulo {k}"})
        assert r.status_code == 200 and r.json()["title"] == f"Titulo {k}" and r.json()["visible"] is True, k
    assert REQUIRED_KEYS <= set(public_keys(c))

    r = c.put("/api/admin/sections/hero", headers=h, json={"content": {"title": "Nuevo"}})
    assert r.status_code == 200 and r.json()["content"] == {"title": "Nuevo"}

    # los módulos adicionales conservan ocultar y borrar
    assert c.post("/api/admin/sections", headers=h, json={"key": "extra", "title": "Extra"}).status_code == 201
    assert c.put("/api/admin/sections/extra", headers=h, json={"visible": False}).status_code == 200
    assert "extra" not in public_keys(c)
    assert c.delete("/api/admin/sections/extra", headers=h).status_code == 204

    # recuperación: una obligatoria borrada y otra oculta directamente en la base
    with SessionLocal() as db:
        db.delete(db.get(Section, "hero"))
        db.get(Section, "contacto").visible = False
        db.commit()
    keys = public_keys(c)
    assert REQUIRED_KEYS <= set(keys), keys
    hero = [s for s in c.get("/api/public/content").json() if s["key"] == "hero"][0]
    assert hero["content"]["title"] == "Ahorra junto a tu cooperativa"

    # recuperación también en el panel y al arrancar
    with SessionLocal() as db:
        db.get(Section, "noticias").visible = False
        db.delete(db.get(Section, "settings"))
        db.commit()
    assert REQUIRED_KEYS <= {s["key"] for s in c.get("/api/admin/sections", headers=h).json()}
    with SessionLocal() as db:
        db.get(Section, "nosotros").visible = False
        db.delete(db.get(Section, "contacto"))
        db.commit()
        seed(db)
    assert REQUIRED_KEYS <= set(public_keys(c))

    # las posiciones siguen siendo únicas y ordenadas
    pos = [s["position"] for s in c.get("/api/admin/sections", headers=h).json()]
    assert pos == sorted(pos) and len(set(pos)) == len(pos), pos
print("OBLIGATORIAS OK")
