"""Reglas de las noticias (id, active, created_at, ventana de 72 h, sin borrar, solo activas al público).
Usa base temporal: DATABASE_URL=sqlite:///./test_tmp.db python test_news_rules.py"""

import copy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import ActivityLog, Section
from app.news import NEWS_EDIT_HOURS, parse_dt
from app.seed import migrate_stored_news

assert NEWS_EDIT_HOURS == 72
tag = uuid4().hex[:6]  # las noticias no se pueden borrar: los títulos llevan una marca para repetir la prueba


def set_created_at(news_id: str, when: datetime) -> None:
    """Retrocede la fecha de creación directamente en la base (el servidor no deja cambiarla)."""
    with SessionLocal() as db:
        section = db.get(Section, "noticias")
        content = copy.deepcopy(section.content)
        for item in content["items"]:
            if item["id"] == news_id:
                item["created_at"] = when.isoformat(timespec="seconds")
        section.content = content
        db.commit()


with TestClient(app, headers={"Origin": "http://localhost:3000"}) as c:
    now = datetime.now(timezone.utc)

    def admin_items():
        sections = c.get("/api/admin/sections").json()
        return next(s for s in sections if s["key"] == "noticias")["content"]["items"]

    def public_items():
        sections = c.get("/api/public/content").json()
        return next(s for s in sections if s["key"] == "noticias")["content"]["items"]

    def save(items, expect=200):
        r = c.put("/api/admin/sections/noticias", json={"content": {"title": "N", "items": items}})
        assert r.status_code == expect, (r.status_code, r.text)
        return r

    assert c.put("/api/admin/sections/noticias", json={"content": {"items": []}}).status_code == 401
    assert (
        c.post(
            "/api/admin/login", json={"email": settings.admin_email, "password": settings.admin_password}
        ).status_code
        == 200
    )

    # 1) las noticias existentes ya traen id, active y created_at (migración del arranque)
    base = admin_items()
    assert base and all(i["active"] is True and len(i["id"]) == 32 and parse_dt(i["created_at"]) for i in base), base
    assert len({i["id"] for i in base}) == len(base)

    # 2) noticia nueva: id, created_at y active=True los pone el servidor, aunque el cliente mande otra cosa
    trampa = {"title": f"Nueva {tag}", "created_at": "2000-01-01T00:00:00+00:00", "active": False, "date": "2001-02-03"}
    r = save(base + [trampa])
    nueva = r.json()["content"]["items"][-1]
    assert nueva["active"] is True and nueva["created_at"] != "2000-01-01T00:00:00+00:00"
    assert abs((parse_dt(nueva["created_at"]) - now).total_seconds()) < 30 and parse_dt(nueva["created_at"]).tzinfo
    assert len(nueva["id"]) == 32 and nueva["date"] == "2001-02-03"
    nid = nueva["id"]
    assert save(base + [{"title": "X", "id": "inventado"}], 422).json()["detail"].count("no existe")  # id desconocido
    assert len(admin_items()) == len(base) + 1  # los rechazos no guardan nada

    # 3) created_at es inmutable
    todas = admin_items()
    for item in todas:
        if item["id"] == nid:
            item["created_at"] = "1999-12-31T00:00:00+00:00"
    assert (
        next(i for i in save(todas).json()["content"]["items"] if i["id"] == nid)["created_at"] == nueva["created_at"]
    )

    # 4) dentro de las 72 h se edita; la fecha de publicación no cuenta para el plazo
    todas = admin_items()
    for item in todas:
        if item["id"] == nid:
            item.update(title=f"Nueva editada {tag}", body="texto", date="2001-02-04")
    assert next(i for i in save(todas).json()["content"]["items"] if i["id"] == nid)["title"] == f"Nueva editada {tag}"

    # 5) pasadas las 72 h el contenido se bloquea, pero active se cambia siempre
    set_created_at(nid, now - timedelta(hours=NEWS_EDIT_HOURS, minutes=1))
    todas = admin_items()
    mine = next(i for i in todas if i["id"] == nid)
    for campo, valor in (
        ("title", "Otro título"),
        ("body", "otro texto"),
        ("date", "2030-01-01"),
        ("image_url", "/uploads/x.png"),
    ):
        cambiada = [{**i, campo: valor} if i["id"] == nid else i for i in todas]
        detail = save(cambiada, 422).json()["detail"]
        assert "ya no se puede editar" in detail and "72 horas" in detail and "Nueva editada" in detail, detail
    assert save(todas).status_code == 200  # el mismo contenido se acepta
    assert save(list(reversed(todas))).status_code == 200  # reordenar no es editar contenido
    sin_slug = [{**i, "slug": ""} if i["id"] == nid else i for i in admin_items()]
    assert next(i for i in save(sin_slug).json()["content"]["items"] if i["id"] == nid)["slug"] == mine["slug"]
    # el límite exacto: 71 h 59 min todavía se edita
    set_created_at(nid, now - timedelta(hours=NEWS_EDIT_HOURS) + timedelta(minutes=1))
    todas = admin_items()
    save([{**i, "title": f"Aún editable {tag}"} if i["id"] == nid else i for i in todas])
    set_created_at(nid, now - timedelta(days=30))  # una noticia muy antigua, para lo que sigue
    todas = admin_items()

    # 6) desactivar y reactivar en cualquier momento, también después de las 72 h
    with c.websocket_connect("/api/public/ws") as ws:
        off = [{**i, "active": False} if i["id"] == nid else i for i in todas]
        r = save(off)
        assert next(i for i in r.json()["content"]["items"] if i["id"] == nid)["active"] is False
        assert nid in [i["id"] for i in admin_items()]  # el panel recibe todas, también las desactivadas
        assert nid not in [i["id"] for i in public_items()]  # el público, solo las activas
        evento = ws.receive_json()
        assert evento["event"] == "section_updated" and evento["data"]["key"] == "noticias"
        assert nid not in [i["id"] for i in evento["data"]["content"]["items"]]  # tampoco por WebSocket
        assert all(i["active"] is True for i in evento["data"]["content"]["items"])
    slug = mine["slug"]
    assert c.get(f"/api/public/news/{slug}").status_code == 404  # ni por slug
    assert c.get(f"/api/public/news/{base[0]['slug']}").status_code == 200

    on = [{**i, "active": True} if i["id"] == nid else i for i in admin_items()]
    save(on)
    assert nid in [i["id"] for i in public_items()]
    assert c.get(f"/api/public/news/{slug}").json()["id"] == nid
    assert save([{**i, "active": "no"} if i["id"] == nid else i for i in admin_items()], 422)  # solo booleanos

    # 7) no se puede borrar ni quitar de la lista
    todas = admin_items()
    for cuantas in (1, len(todas)):
        detail = save(todas[: len(todas) - cuantas], 422).json()["detail"]
        assert "No se pueden eliminar" in detail and "active=false" in detail, detail
    assert save(todas + [todas[0]], 422).json()["detail"].count("repetido")
    assert c.put("/api/admin/sections/noticias", json={"content": {"title": "N", "items": "x"}}).status_code == 422
    assert c.delete("/api/admin/sections/noticias").status_code == 403
    assert len(admin_items()) == len(todas)

    # 8) la bitácora cuenta qué pasó con las noticias
    cambios = c.get("/api/admin/activity?action=section_update&entity_key=noticias&limit=50").json()["items"]
    resumen = [i["details"].get("news", {}) for i in cambios]
    assert any("created" in r for r in resumen) and any("deactivated" in r for r in resumen)
    assert any("activated" in r for r in resumen) and any("edited" in r for r in resumen)

    # 9) migración de noticias antiguas: no usa la fecha de publicación y es idempotente
    with SessionLocal() as db:
        section = db.get(Section, "noticias")
        legacy = copy.deepcopy(section.content)
        legacy["items"] = [
            {"title": "Antigua A", "slug": "antigua-a", "date": "2020-01-01"},
            {
                "title": "Antigua B",
                "slug": "antigua-b",
                "date": "2020-02-02",
                "active": False,
                "created_at": "2024-05-05T10:00:00+00:00",
            },
            {"title": "Antigua C", "slug": "antigua-c", "created_at": "basura", "id": "abc"},
        ]
        section.content = legacy
        db.commit()
        antes = datetime.now(timezone.utc)
        assert migrate_stored_news(db) == 3
        items = db.get(Section, "noticias").content["items"]
        a, b, cc = items
        assert len(a["id"]) == 32 and a["active"] is True
        assert (
            antes - timedelta(seconds=5)
            <= parse_dt(a["created_at"])
            <= datetime.now(timezone.utc) + timedelta(seconds=5)
        )
        assert not a["created_at"].startswith("2020"), a  # la fecha de publicación no se usa
        assert b["active"] is False and b["created_at"] == "2024-05-05T10:00:00+00:00" and len(b["id"]) == 32
        assert cc["id"] == "abc" and parse_dt(cc["created_at"]) is not None
        assert migrate_stored_news(db) == 0  # segunda vez: no cambia nada
        assert db.query(ActivityLog).filter(ActivityLog.action == "news_migration").count() >= 1

        # con una fecha de respaldo acordada en NEWS_CREATED_AT_FALLBACK
        section = db.get(Section, "noticias")
        legacy = copy.deepcopy(section.content)
        legacy["items"] = [{"title": "Otra antigua", "slug": "otra-antigua"}]
        section.content = legacy
        db.commit()
        settings.news_created_at_fallback = "2026-10-01T00:00:00Z"
        try:
            assert migrate_stored_news(db) == 1
        finally:
            settings.news_created_at_fallback = ""
        assert db.get(Section, "noticias").content["items"][0]["created_at"] == "2026-10-01T00:00:00+00:00"
print("REGLAS DE NOTICIAS OK")
