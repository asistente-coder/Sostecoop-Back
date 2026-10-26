import re
import unicodedata
from datetime import date

from fastapi import HTTPException


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _fail(msg: str):
    raise HTTPException(422, msg)


def validate_news(content: dict) -> dict:
    """Valida los items de la sección «noticias» y completa el slug cuando viene vacío."""
    items = content.get("items", [])
    if not isinstance(items, list):
        _fail("noticias.items debe ser una lista")

    explicit = set()
    for n, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            _fail(f"Noticia {n}: formato inválido")
        if not str(item.get("title", "")).strip():
            _fail(f"Noticia {n}: falta el título")
        slug = slugify(str(item.get("slug", "")))
        if slug:
            if slug in explicit:
                _fail(f"Noticia {n}: el slug «{slug}» está repetido")
            explicit.add(slug)
        item["slug"] = slug
        d = str(item.get("date", "")).strip()
        if d:
            try:
                date.fromisoformat(d)
            except ValueError:
                _fail(f"Noticia {n}: la fecha debe tener formato AAAA-MM-DD")

    used = set(explicit)
    for n, item in enumerate(items, start=1):
        if item["slug"]:
            continue
        base = slugify(item["title"])
        if not base:
            _fail(f"Noticia {n}: el título no permite generar un slug, escríbelo a mano")
        slug, k = base, 2
        while slug in used:
            slug, k = f"{base}-{k}", k + 1
        used.add(slug)
        item["slug"] = slug
    return content
