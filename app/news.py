import copy
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

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


NEWS_EDIT_HOURS = 72
# Campos del servidor: id y created_at no los cambia el frontend; active sí, pero solo con un booleano
MANAGED_FIELDS = frozenset({"id", "created_at", "active"})


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_dt(value) -> datetime | None:
    """Lee una fecha ISO 8601. Sin zona horaria se interpreta como UTC. None si no es una fecha válida."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def is_locked(item: dict, now: datetime) -> bool:
    """El contenido se puede editar durante 72 h desde `created_at` (no desde la fecha de publicación)."""
    created = parse_dt(item.get("created_at"))
    return created is not None and now - created > timedelta(hours=NEWS_EDIT_HOURS)


def _content(item: dict) -> dict:
    """Lo que cuenta como contenido: todo menos los campos del servidor. Un campo vacío equivale a uno ausente."""
    return {k: v for k, v in item.items() if k not in MANAGED_FIELDS and v not in (None, "")}


def _title(item: dict) -> str:
    return str(item.get("title", "")).strip() or "(sin título)"


def migrate_news_items(content: dict, fallback: datetime) -> int:
    """Completa id, active y created_at en las noticias que no los tengan. Devuelve cuántas noticias cambió.

    No usa la fecha de publicación (`date`), que es editable: sin una fecha real de creación se usa `fallback`.
    """
    items = content.get("items")
    if not isinstance(items, list):
        return 0
    changed = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        touched = False
        if not (isinstance(item.get("id"), str) and item["id"]):
            item["id"] = uuid4().hex
            touched = True
        if not isinstance(item.get("active"), bool):
            item["active"] = True
            touched = True
        if parse_dt(item.get("created_at")) is None:
            item["created_at"] = fallback.astimezone(timezone.utc).isoformat(timespec="seconds")
            touched = True
        changed += touched
    return changed


def migrate_content(content: dict, fallback: datetime) -> tuple[dict, int]:
    """Copia el contenido y le completa los campos de las noticias. Devuelve (copia, noticias cambiadas)."""
    clone = copy.deepcopy(content)
    return clone, migrate_news_items(clone, fallback)


def news_fallback(configured: str) -> datetime:
    """Fecha de creación para las noticias antiguas: la configurada o, si no hay, ahora."""
    if not configured.strip():
        return utc_now()
    parsed = parse_dt(configured)
    if parsed is None:
        raise ValueError("NEWS_CREATED_AT_FALLBACK no es una fecha ISO 8601 válida (ej.: 2026-10-01T00:00:00+00:00)")
    return parsed


MAX_CATEGORY_LENGTH = 40


def _norm(text) -> str:
    """Forma en que se comparan las categorías: sin mayúsculas y sin espacios de más."""
    return " ".join(str(text or "").split()).casefold()


def validate_categories(value) -> list[str]:
    """`content.categories`: lista de textos no vacíos, de máximo 40 caracteres y sin repetidos."""
    if not isinstance(value, list):
        _fail("noticias.categories debe ser una lista de textos")
    cleaned: list[str] = []
    seen: dict[str, str] = {}
    for n, raw in enumerate(value, start=1):
        if not isinstance(raw, str):
            _fail(f"Categoría {n}: debe ser un texto")
        name = raw.strip()
        if not name:
            _fail(f"Categoría {n}: no puede estar vacía")
        if len(name) > MAX_CATEGORY_LENGTH:
            _fail(f"Categoría {n}: «{name[:20]}…» tiene {len(name)} caracteres (máximo {MAX_CATEGORY_LENGTH})")
        key = _norm(name)
        if key in seen:
            _fail(f"Categoría {n}: «{name}» está repetida; ya existe «{seen[key]}» (se ignoran mayúsculas/espacios)")
        seen[key] = name
        cleaned.append(name)
    return cleaned


def check_categories_in_use(old_categories: list[str], new_categories: list[str], items: list[dict]) -> None:
    """Rechaza quitar una categoría que todavía tiene noticias asignadas (cuenta el estado final de las noticias)."""
    kept = {_norm(name) for name in new_categories}
    for name in old_categories:
        if _norm(name) in kept:
            continue
        users = [_title(item) for item in items if _norm(item.get("category")) == _norm(name)]
        if users:
            shown = ", ".join(f"«{title}»" for title in users[:3]) + ("…" if len(users) > 3 else "")
            _fail(
                f"No se puede eliminar la categoría «{name}»: la usan {len(users)} noticia(s) ({shown}). "
                "Cambia la categoría de esas noticias antes de eliminarla"
            )


def apply_news_rules(old: dict, new: dict, now: datetime | None = None) -> tuple[dict, dict]:
    """Reglas del servidor para guardar la sección «noticias». Devuelve (contenido, resumen de cambios).

    - Cada noticia se identifica por su `id`; las que llegan sin `id` son nuevas y reciben id, created_at (hora del
      servidor) y active=True. Un `id` desconocido se rechaza.
    - `created_at` es inmutable: se ignora lo que mande el cliente.
    - Ninguna noticia se puede quitar de la lista (hay que desactivarla con `active`).
    - `active` se puede cambiar siempre. El resto del contenido, solo durante 72 h desde `created_at`.
    - `content.categories` se valida y se conserva: si no llega en la petición se mantiene la guardada, y no se puede
      quitar una categoría que alguna noticia siga usando.
    """
    now = now or utc_now()
    new_items = new.get("items", [])
    if not isinstance(new_items, list):
        _fail("noticias.items debe ser una lista")
    for n, item in enumerate(new_items, start=1):
        if not isinstance(item, dict):
            _fail(f"Noticia {n}: formato inválido")

    old_by_id = {i["id"]: i for i in old.get("items", []) if isinstance(i, dict) and i.get("id")}
    seen: set[str] = set()
    for n, item in enumerate(new_items, start=1):
        news_id = item.get("id")
        if news_id in (None, ""):
            continue
        if not isinstance(news_id, str) or news_id not in old_by_id:
            _fail(f"Noticia {n}: el id «{news_id}» no existe; las noticias nuevas van sin id (lo asigna el servidor)")
        if news_id in seen:
            _fail(f"Noticia {n}: el id «{news_id}» está repetido")
        seen.add(news_id)

    missing = [_title(i) for news_id, i in old_by_id.items() if news_id not in seen]
    if missing:
        _fail(
            "No se pueden eliminar noticias ni quitarlas de la lista: "
            + ", ".join(f"«{title}»" for title in missing)
            + ". Para ocultarlas al público, desactívalas con active=false"
        )

    created_at = now.astimezone(timezone.utc).isoformat(timespec="seconds")
    for n, item in enumerate(new_items, start=1):
        stored = old_by_id.get(item.get("id"))
        if stored is None:  # noticia nueva: lo que mande el cliente en estos campos se ignora
            item["id"], item["created_at"], item["active"] = uuid4().hex, created_at, True
            continue
        item["created_at"] = stored.get("created_at")
        if "active" in item and not isinstance(item["active"], bool):
            _fail(f"Noticia {n}: active debe ser true o false")
        item["active"] = item.get("active", stored.get("active", True))
        if is_locked(stored, now) and not str(item.get("slug", "")).strip():
            item["slug"] = stored.get("slug", "")  # un slug vacío no debe regenerarse en una noticia ya cerrada

    validate_news(new)

    stored_categories = old.get("categories")
    old_categories = [c for c in stored_categories if isinstance(c, str)] if isinstance(stored_categories, list) else []
    if new.get("categories") is not None:
        new["categories"] = validate_categories(new["categories"])
        check_categories_in_use(old_categories, new["categories"], new_items)
    elif "categories" in old:
        new["categories"] = copy.deepcopy(old["categories"])  # guardar sin enviarlas no las borra
    else:
        new.pop("categories", None)

    summary: dict[str, list[str]] = {
        "created": [],
        "edited": [],
        "activated": [],
        "deactivated": [],
        "categories_added": [],
        "categories_removed": [],
    }
    before = {_norm(c): c for c in old_categories}
    after = {_norm(c): c for c in new.get("categories", []) if isinstance(c, str)}
    summary["categories_added"] = [name for key, name in after.items() if key not in before]
    summary["categories_removed"] = [name for key, name in before.items() if key not in after]
    for item in new_items:
        stored = old_by_id.get(item["id"])
        if stored is None:
            summary["created"].append(_title(item))
            continue
        if _content(item) != _content(stored):
            if is_locked(stored, now):
                _fail(
                    f"La noticia «{_title(stored)}» ya no se puede editar: pasaron más de {NEWS_EDIT_HOURS} horas "
                    "desde su creación. Solo se puede activar o desactivar"
                )
            summary["edited"].append(_title(item))
        was_active = stored.get("active", True)
        if was_active != item["active"]:
            summary["activated" if item["active"] else "deactivated"].append(_title(item))
    return new, {k: v for k, v in summary.items() if v}


def public_news(content: dict) -> dict:
    """El contenido de «noticias» tal como lo ve el público: solo las noticias activas."""
    items = content.get("items")
    if not isinstance(items, list):
        return content
    return {**content, "items": [i for i in items if not isinstance(i, dict) or i.get("active", True) is True]}


def public_section(data: dict) -> dict:
    """Una sección (como diccionario) lista para el público: oculta las noticias desactivadas."""
    if data.get("key") != "noticias":
        return data
    return {**data, "content": public_news(data.get("content") or {})}
