import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from .config import settings
from .models import ActivityLog, Admin, Section
from .news import migrate_content, news_fallback
from .security import hash_password

log = logging.getLogger("uvicorn.error")

# Contenido inicial. Ajustar las llaves a lo que muestre el diseño de Figma.
DEFAULT_SECTIONS = [
    (
        "settings",
        "Ajustes generales",
        {
            "site_name": "Cooperativa de Ahorro",
            "logo_url": "",
            "menu": [
                {"label": "Inicio", "anchor": "#inicio"},
                {"label": "Nosotros", "anchor": "#nosotros"},
                {"label": "Servicios", "anchor": "#servicios"},
                {"label": "Contacto", "anchor": "#contacto"},
            ],
            "footer_text": "© Cooperativa de Ahorro. Todos los derechos reservados.",
            "social": {"facebook": "", "instagram": "", "whatsapp": ""},
        },
    ),
    (
        "hero",
        "Inicio",
        {
            "title": "Ahorra junto a tu cooperativa",
            "subtitle": "Crece con nosotros de forma segura y solidaria.",
            "cta_label": "Contáctanos",
            "cta_anchor": "#contacto",
            "image_url": "",
        },
    ),
    (
        "nosotros",
        "Nosotros",
        {
            "title": "Quiénes somos",
            "text": "Somos una cooperativa creada por y para sus asociados.",
            "mission": "",
            "vision": "",
            "image_url": "",
        },
    ),
    (
        "servicios",
        "Servicios",
        {
            "title": "Nuestros servicios",
            "items": [
                {"icon": "piggy-bank", "title": "Ahorro programado", "text": "Ahorra de forma constante."},
                {"icon": "hand-coins", "title": "Créditos", "text": "Tasas justas para asociados."},
            ],
        },
    ),
    (
        "beneficios",
        "Beneficios",
        {
            "title": "Por qué elegirnos",
            "items": [{"title": "Transparencia", "text": "Cuentas claras."}],
        },
    ),
    ("noticias", "Noticias", json.loads((Path(__file__).parent / "noticias_seed.json").read_text(encoding="utf-8"))),
    (
        "testimonios",
        "Testimonios",
        {
            "title": "Lo que dicen nuestros asociados",
            "items": [{"name": "Asociado", "text": "Excelente servicio.", "photo_url": ""}],
        },
    ),
    (
        "faq",
        "Preguntas frecuentes",
        {
            "title": "Preguntas frecuentes",
            "items": [{"question": "¿Cómo me asocio?", "answer": "Escríbenos desde el formulario de contacto."}],
        },
    ),
    (
        "contacto",
        "Contacto",
        {
            "title": "Contáctanos",
            "subtitle": "Te respondemos lo antes posible.",
            "address": "",
            "phone": "",
            "email": "",
            "schedule": "",
            "map_url": "",
        },
    ),
]


# Secciones que el sitio necesita siempre: no se pueden borrar ni ocultar
REQUIRED_KEYS = frozenset({"settings", "hero", "nosotros", "noticias", "contacto"})


def _insert_default(db: Session, index: int) -> None:
    key, title, content = DEFAULT_SECTIONS[index]
    if key == "noticias":  # las noticias nacen con id, active y created_at
        content, _ = migrate_content(content, news_fallback(settings.news_created_at_fallback))
    db.query(Section).filter(Section.position >= index).update({Section.position: Section.position + 1})
    db.add(Section(key=key, title=title, content=content, position=index))
    db.flush()


def ensure_required_sections(db: Session) -> bool:
    """Recrea las secciones obligatorias que falten y vuelve a mostrar las que estén ocultas."""
    changed = False
    for index, (key, _, _) in enumerate(DEFAULT_SECTIONS):
        if key not in REQUIRED_KEYS:
            continue
        section = db.get(Section, key)
        if section is None:
            _insert_default(db, index)
            changed = True
        elif not section.visible:
            section.visible = True
            changed = True
    if changed:
        db.commit()
    return changed


def migrate_stored_news(db: Session) -> int:
    """Completa id, active y created_at en las noticias ya guardadas que no los tengan. Es idempotente.

    Las noticias antiguas no guardan su fecha real de creación (`date` es la de publicación, editable), así que
    reciben la fecha de NEWS_CREATED_AT_FALLBACK o, si no está definida, el momento de la migración.
    """
    section = db.get(Section, "noticias")
    if section is None:
        return 0
    fallback = news_fallback(settings.news_created_at_fallback)
    content, changed = migrate_content(section.content or {}, fallback)
    if not changed:
        return 0
    section.content = content  # objeto nuevo, para que SQLAlchemy detecte el cambio del JSON
    db.add(
        ActivityLog(
            action="news_migration",
            entity_type="section",
            entity_key="noticias",
            summary=f"Migración: se completaron id, active y created_at en {changed} noticia(s)",
            details={"news": changed, "created_at": fallback.isoformat(timespec="seconds")},
        )
    )
    db.commit()
    log.info("Noticias migradas: %s (created_at asignado: %s)", changed, fallback.isoformat(timespec="seconds"))
    return changed


def seed(db: Session) -> None:
    if not db.query(Admin).first():
        db.add(Admin(email=settings.admin_email, password_hash=hash_password(settings.admin_password)))
    # Crea las secciones que falten (también en bases ya existentes), respetando el orden del seed
    for index, (key, _, _) in enumerate(DEFAULT_SECTIONS):
        if not db.get(Section, key):
            _insert_default(db, index)
    db.commit()
    ensure_required_sections(db)
    migrate_stored_news(db)
