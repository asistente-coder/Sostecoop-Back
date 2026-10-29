"""Validación de noticias. Usa una base temporal: DATABASE_URL=sqlite:///./test_tmp.db python test_news.py"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

tag = uuid4().hex[:6]  # las noticias no se pueden borrar: los títulos llevan una marca para repetir la prueba

with TestClient(app) as c:
    c.headers["Origin"] = "http://localhost:3000"
    keys = [s["key"] for s in c.get("/api/public/content").json()]
    assert "noticias" in keys and keys.index("noticias") == keys.index("beneficios") + 1, keys

    assert (
        c.post(
            "/api/admin/login", json={"email": settings.admin_email, "password": settings.admin_password}
        ).status_code
        == 200
    )

    def existing():
        sections = c.get("/api/admin/sections").json()
        return next(s for s in sections if s["key"] == "noticias")["content"]["items"]

    # el guardado envía la lista completa: las noticias que ya existen (con su id) más las nuevas
    put = lambda items: c.put(
        "/api/admin/sections/noticias", json={"content": {"title": "N", "items": existing() + items}}
    )

    assert put([{"title": ""}]).status_code == 422
    assert put([{"title": "A", "slug": "x"}, {"title": "B", "slug": "X"}]).status_code == 422
    assert put([{"title": "A", "date": "12/06/2025"}]).status_code == 422

    r = put(
        [
            {"title": f"Cinco hábitos de ahorro {tag}"},
            {"title": f"Cinco hábitos de ahorro {tag}"},
            {"title": "Otra", "slug": f"Mi Slug ÁÉ {tag}"},
        ]
    )
    assert r.status_code == 200, r.text
    slugs = [i["slug"] for i in r.json()["content"]["items"]][-3:]
    assert slugs == [f"cinco-habitos-de-ahorro-{tag}", f"cinco-habitos-de-ahorro-{tag}-2", f"mi-slug-ae-{tag}"], slugs
print("NOTICIAS OK")
