from datetime import datetime, timezone

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(String(300))


class Section(Base):
    """Cada bloque editable de la web (hero, servicios, contacto, ...)."""

    __tablename__ = "sections"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ActivityLog(Base):
    """Bitácora de lo que hace el administrador: quién, qué, sobre qué, desde dónde y cuándo.

    Solo se inserta (nunca se edita ni se borra desde la API). `admin_email` guarda el correo y no una
    llave foránea, así el historial se conserva aunque el administrador cambie o se elimine.
    """

    __tablename__ = "activity_log"
    __table_args__ = (
        Index("ix_activity_log_created_at", "created_at"),
        Index("ix_activity_log_action", "action"),
        Index("ix_activity_log_entity", "entity_type", "entity_key"),
        Index("ix_activity_log_admin_email", "admin_email"),
    )

    # BigInteger en PostgreSQL; SQLite (pruebas) solo autoincrementa con INTEGER
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    admin_email: Mapped[str | None] = mapped_column(String(200), nullable=True)  # None: intento sin sesión
    action: Mapped[str] = mapped_column(String(40))  # login, section_update, upload, ...
    entity_type: Mapped[str | None] = mapped_column(String(30), nullable=True)  # section, contact, file
    entity_key: Mapped[str | None] = mapped_column(String(100), nullable=True)  # clave, id o ruta afectada
    summary: Mapped[str] = mapped_column(String(300))  # frase legible para mostrar en el panel
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # antes/después y otros datos
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, server_default=func.now())
