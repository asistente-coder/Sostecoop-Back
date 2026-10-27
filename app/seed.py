import json
from pathlib import Path

from sqlalchemy.orm import Session

from .config import settings
from .models import Admin, Section
from .security import hash_password

# Contenido inicial. Ajustar las llaves a lo que muestre el diseño de Figma.
DEFAULT_SECTIONS = [
    ("settings", "Ajustes generales", {
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
    }),
    ("hero", "Inicio", {
        "title": "Ahorra junto a tu cooperativa",
        "subtitle": "Crece con nosotros de forma segura y solidaria.",
        "cta_label": "Contáctanos",
        "cta_anchor": "#contacto",
        "image_url": "",
    }),
    ("nosotros", "Nosotros", {
        "title": "Quiénes somos",
        "text": "Somos una cooperativa creada por y para sus asociados.",
        "mission": "",
        "vision": "",
        "image_url": "",
    }),
    ("servicios", "Servicios", {
        "title": "Nuestros servicios",
        "items": [
            {"icon": "piggy-bank", "title": "Ahorro programado", "text": "Ahorra de forma constante."},
            {"icon": "hand-coins", "title": "Créditos", "text": "Tasas justas para asociados."},
        ],
    }),
    ("beneficios", "Beneficios", {
        "title": "Por qué elegirnos",
        "items": [{"title": "Transparencia", "text": "Cuentas claras."}],
    }),
    ("noticias", "Noticias", json.loads((Path(__file__).parent / "noticias_seed.json").read_text(encoding="utf-8"))),
    ("testimonios", "Testimonios", {
        "title": "Lo que dicen nuestros asociados",
        "items": [{"name": "Asociado", "text": "Excelente servicio.", "photo_url": ""}],
    }),
    ("faq", "Preguntas frecuentes", {
        "title": "Preguntas frecuentes",
        "items": [{"question": "¿Cómo me asocio?", "answer": "Escríbenos desde el formulario de contacto."}],
    }),
    ("contacto", "Contacto", {
        "title": "Contáctanos",
        "subtitle": "Te respondemos lo antes posible.",
        "address": "",
        "phone": "",
        "email": "",
        "schedule": "",
        "map_url": "",
    }),
]


# Secciones que el sitio necesita siempre: no se pueden borrar ni ocultar
REQUIRED_KEYS = frozenset({"settings", "hero", "nosotros", "noticias", "contacto"})


def _insert_default(db: Session, index: int) -> None:
    key, title, content = DEFAULT_SECTIONS[index]
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


def seed(db: Session) -> None:
    if not db.query(Admin).first():
        db.add(Admin(email=settings.admin_email, password_hash=hash_password(settings.admin_password)))
    # Crea las secciones que falten (también en bases ya existentes), respetando el orden del seed
    for index, (key, _, _) in enumerate(DEFAULT_SECTIONS):
        if not db.get(Section, key):
            _insert_default(db, index)
    db.commit()
    ensure_required_sections(db)
