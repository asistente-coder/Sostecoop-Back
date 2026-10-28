from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from .models import ActivityLog, Section

FIELD_LABELS = {"title": "título", "visible": "visibilidad", "position": "posición"}


def log_activity(
    db: Session,
    request: Request,
    email: str | None,
    action: str,
    summary: str,
    entity_type: str | None = None,
    entity_key: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Agrega el registro a la sesión. No hace commit: se guarda junto con el cambio que describe."""
    db.add(
        ActivityLog(
            admin_email=email,
            action=action,
            entity_type=entity_type,
            entity_key=entity_key,
            summary=summary[:300],
            details=details,
            ip=request.client.host if request.client else None,
        )
    )


def section_changes(section: Section, changes: dict[str, Any]) -> dict[str, Any]:
    """Compara una sección con los cambios pedidos y devuelve solo lo que cambia de verdad.

    Para title, visible y position guarda el antes y el después. El contenido puede ser enorme,
    así que solo se anotan los nombres de los campos que cambiaron.
    """
    diff: dict[str, Any] = {}
    for field in FIELD_LABELS:
        if field in changes and changes[field] != getattr(section, field):
            diff[field] = {"before": getattr(section, field), "after": changes[field]}

    new_content = changes.get("content")
    if new_content is not None:
        old_content = section.content or {}
        keys = sorted(k for k in old_content.keys() | new_content.keys() if old_content.get(k) != new_content.get(k))
        if keys:
            diff["content_fields"] = keys
    return diff


def section_summary(key: str, diff: dict[str, Any]) -> str:
    parts = []
    for field, label in FIELD_LABELS.items():
        if field in diff:
            parts.append(label)
    if "content_fields" in diff:
        parts.append("contenido (" + ", ".join(diff["content_fields"]) + ")")
    return f"Editó la sección «{key}»: " + ", ".join(parts)
