"""Categorías de noticias (content.categories). Usa base temporal:
DATABASE_URL=sqlite:///./test_tmp.db python test_news_categories.py"""

import copy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import Section

tag = uuid4().hex[:6]  # las noticias no se borran: las categorías llevan una marca para poder repetir la prueba


def lock_news(news_id: str) -> None:
    """Hace «vieja» una noticia directamente en la base (el servidor no deja cambiar created_at)."""
    with SessionLocal() as db:
        section = db.get(Section, "noticias")
        content = copy.deepcopy(section.content)
        for item in content["items"]:
            if item["id"] == news_id:
                item["created_at"] = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(timespec="seconds")
        section.content = content
        db.commit()


with TestClient(app, headers={"Origin": "http://localhost:3000"}) as c:
    assert (
        c.post(
            "/api/admin/login", json={"email": settings.admin_email, "password": settings.admin_password}
        ).status_code
        == 200
    )

    def content_of(path):
        return next(s for s in c.get(path).json() if s["key"] == "noticias")["content"]

    admin_content = lambda: content_of("/api/admin/sections")
    items = lambda: admin_content()["items"]
    cats = lambda: admin_content().get("categories")

    def put(items_=None, **extra):
        body = {"title": "N", "items": items() if items_ is None else items_, **extra}
        return c.put("/api/admin/sections/noticias", json={"content": body})

    def ok(items_=None, **extra):
        r = put(items_, **extra)
        assert r.status_code == 200, (r.status_code, r.text)
        return r.json()["content"]

    def bad(needle, items_=None, **extra):
        before = admin_content()
        r = put(items_, **extra)
        assert r.status_code == 422, (r.status_code, r.text)
        assert needle in r.json()["detail"], r.json()["detail"]
        assert admin_content() == before  # lo rechazado no se guarda

    def used():
        names = {}
        for item in items():
            name = " ".join(str(item.get("category") or "").split())
            if name:
                names.setdefault(name.casefold(), name)
        return list(names.values())

    # base: las categorías que ya usa alguna noticia (de otras pruebas) deben seguir en la lista
    base = []
    for name in list(cats() or []) + used():
        if name.casefold() not in {b.casefold() for b in base}:
            base.append(name)

    # 1) se guardan, se devuelven y las ve el público
    nuevas = base + [f"Ahorro {tag}", f"Crédito {tag}"]
    assert ok(categories=nuevas)["categories"] == nuevas
    assert cats() == nuevas and content_of("/api/public/content")["categories"] == nuevas

    # 2) guardar sin enviarlas (o con null) no las borra
    assert ok()["categories"] == nuevas
    assert ok(categories=None)["categories"] == nuevas
    assert cats() == nuevas
    assert c.put("/api/admin/sections/noticias", json={"title": "Noticias"}).status_code == 200  # solo el título
    assert cats() == nuevas

    # 3) validaciones
    for malo in ("texto", {"a": 1}, 5):
        bad("lista de textos", categories=malo)
    bad("debe ser un texto", categories=nuevas + [5])
    bad("no puede estar vacía", categories=nuevas + [""])
    bad("no puede estar vacía", categories=nuevas + ["   "])
    bad("máximo 40", categories=nuevas + ["x" * 41])
    limite = f"{tag}-" + "x" * (40 - len(tag) - 1)
    assert len(limite) == 40
    assert limite in ok(categories=nuevas + [limite])["categories"]  # 40 caracteres: se acepta
    for repetida in (f"ahorro {tag}", f" AHORRO {tag} ", f"Ahorro   {tag}", f"AHORRO\t{tag}"):
        bad("repetida", categories=nuevas + [repetida])
    bad("repetida", categories=nuevas + [f"Mismo {tag}", f"mismo {tag}"])
    assert f"Credito {tag}" in ok(categories=nuevas + [f"Credito {tag}"])["categories"]  # sin tilde es otra categoría
    nuevas = nuevas + [f"Credito {tag}"]
    assert ok(categories=nuevas)["categories"] == nuevas
    assert (
        f"Salud {tag}" in ok(categories=nuevas + [f"  Salud {tag}  "])["categories"]
    )  # se guarda sin espacios sobrantes
    nuevas = nuevas + [f"Salud {tag}"]

    # 4) una categoría nueva sirve para las noticias en cuanto se guarda; el category de cada noticia se conserva
    nueva_cat = f"Nueva {tag}"
    noticia = {"title": f"Con categoría {tag}", "category": nueva_cat}
    r = ok(items() + [noticia], categories=nuevas + [nueva_cat])
    asignada = r["items"][-1]
    assert asignada["category"] == nueva_cat and nueva_cat in r["categories"]
    assert next(i for i in items() if i["id"] == asignada["id"])["category"] == nueva_cat  # al volver a cargar
    antes = {i["id"]: i.get("category") for i in items()}
    ok(categories=nuevas + [nueva_cat, f"Otra {tag}"])
    assert {i["id"]: i.get("category") for i in items()} == antes  # guardar categorías no toca las noticias
    nuevas = nuevas + [nueva_cat, f"Otra {tag}"]

    # 5) no se puede eliminar una categoría que alguna noticia usa
    sin_nueva = [n for n in nuevas if n != nueva_cat]
    bad(f"No se puede eliminar la categoría «{nueva_cat}»", categories=sin_nueva)
    bad(f"Con categoría {tag}", categories=sin_nueva)  # dice qué noticia la usa
    bad("No se puede eliminar", categories=[])  # quitarlas todas tampoco, mientras haya noticias asignadas
    sin_otra = [n for n in nuevas if n != f"Otra {tag}"]
    assert f"Otra {tag}" not in ok(categories=sin_otra)["categories"]  # una sin uso sí se elimina
    nuevas = sin_otra
    # reasignar la noticia y quitar la categoría en el mismo guardado es válido (cuenta el estado final)
    otra = [{**i, "category": f"Salud {tag}"} if i["id"] == asignada["id"] else i for i in items()]
    assert nueva_cat not in ok(otra, categories=sin_nueva)["categories"]
    nuevas = sin_nueva

    # la comparación ignora mayúsculas y espacios, y una noticia desactivada también cuenta
    raro = [
        {**i, "category": f"  AHORRO   {tag} ", "active": False} if i["id"] == asignada["id"] else i for i in items()
    ]
    ok(raro)
    bad(f"No se puede eliminar la categoría «Ahorro {tag}»", categories=[n for n in nuevas if n != f"Ahorro {tag}"])
    ok(categories=nuevas)

    # una noticia cerrada (pasadas las 72 h) no puede cambiar de categoría, así que su categoría tampoco se elimina
    cerrada_cat = f"Cerrada {tag}"
    r = ok(items() + [{"title": f"Cerrada {tag}", "category": cerrada_cat}], categories=nuevas + [cerrada_cat])
    cerrada = r["items"][-1]
    lock_news(cerrada["id"])
    nuevas = nuevas + [cerrada_cat]
    bad("la usan", categories=[n for n in nuevas if n != cerrada_cat])
    cambiada = [{**i, "category": f"Salud {tag}"} if i["id"] == cerrada["id"] else i for i in items()]
    bad("ya no se puede editar", cambiada)

    # el WebSocket público trae las categorías, y la bitácora cuenta qué se agregó y qué se quitó
    with c.websocket_connect("/api/public/ws") as ws:
        ok(categories=nuevas + [f"Ws {tag}"])
        evento = ws.receive_json()
        assert evento["data"]["key"] == "noticias" and f"Ws {tag}" in evento["data"]["content"]["categories"]
    ok(categories=nuevas)
    cambios = c.get("/api/admin/activity?action=section_update&entity_key=noticias&limit=20").json()["items"]
    resumen = [i["details"].get("news", {}) for i in cambios]
    assert any(f"Ws {tag}" in r.get("categories_added", []) for r in resumen)
    assert any(f"Ws {tag}" in r.get("categories_removed", []) for r in resumen)
print("CATEGORIAS OK")
