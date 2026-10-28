"""Prueba de la sección noticias. Usa una base temporal: DATABASE_URL=sqlite:///./test_tmp.db python test_news.py"""

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

with TestClient(app) as c:
    c.headers["Origin"] = "http://localhost:3000"
    keys = [s["key"] for s in c.get("/api/public/content").json()]
    assert "noticias" in keys and keys.index("noticias") == keys.index("beneficios") + 1, keys

    assert (
        c.post("/api/admin/login", json={"email": settings.admin_email, "password": settings.admin_password}).status_code
        == 200
    )
    h = {}  # la sesión va en la cookie
    put = lambda items: c.put(
        "/api/admin/sections/noticias", headers=h, json={"content": {"title": "N", "items": items}}
    )

    assert put([{"title": ""}]).status_code == 422
    assert put([{"title": "A", "slug": "x"}, {"title": "B", "slug": "X"}]).status_code == 422
    assert put([{"title": "A", "date": "12/06/2025"}]).status_code == 422

    r = put(
        [
            {"title": "Cinco hábitos de ahorro"},
            {"title": "Cinco hábitos de ahorro"},
            {"title": "Otra", "slug": "Mi Slug ÁÉ"},
        ]
    )
    assert r.status_code == 200, r.text
    slugs = [i["slug"] for i in r.json()["content"]["items"]]
    assert slugs == ["cinco-habitos-de-ahorro", "cinco-habitos-de-ahorro-2", "mi-slug-ae"], slugs
print("NOTICIAS OK")
