import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..activity import log_activity, section_changes, section_summary
from ..database import get_db
from ..models import ActivityLog, Admin, ContactMessage, Section
from ..menu import validate_menu
from ..news import apply_news_rules, public_section
from ..realtime import hub
from ..schemas import (
    ActivityPage,
    ContactOut,
    LoginIn,
    SectionCreate,
    SectionOut,
    SectionUpdate,
    SessionOut,
)
from ..security import (
    COOKIE_NAME,
    clear_session_cookie,
    create_token,
    csrf_protect,
    current_admin,
    decode_token,
    set_session_cookie,
    verify_password,
)
from ..seed import REQUIRED_KEYS, ensure_required_sections

router = APIRouter(prefix="/api/admin", tags=["Admin"], dependencies=[Depends(csrf_protect)])
UPLOADS = Path("uploads")
ALLOWED = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
MAX_BYTES = 5 * 1024 * 1024


@router.post("/login", response_model=SessionOut)
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    """Valida las credenciales y guarda el JWT en la cookie HttpOnly `sostecoop_admin` (no va en el cuerpo)."""
    admin = db.query(Admin).filter(Admin.email == data.email).first()
    if not admin or not verify_password(data.password, admin.password_hash):
        # Sin sesión: el correo intentado va en details (puede no existir), nunca la contraseña
        log_activity(
            db,
            request,
            None,
            "login_failed",
            "Intento de inicio de sesión fallido",
            "session",
            details={"email": data.email[:200]},
        )
        db.commit()
        raise HTTPException(401, "Credenciales incorrectas")
    set_session_cookie(response, create_token(admin.email))
    log_activity(db, request, admin.email, "login", "Inició sesión", "session")
    db.commit()
    return {"email": admin.email}


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """Cierra la sesión borrando la cookie (mismos path, SameSite y Secure con los que se creó)."""
    token = request.cookies.get(COOKIE_NAME)
    email = decode_token(token) if token else None
    if email:
        log_activity(db, request, email, "logout", "Cerró sesión", "session")
        db.commit()
    clear_session_cookie(response)


@router.get("/me", response_model=SessionOut)
def me(admin: Admin = Depends(current_admin)):
    """Sirve para comprobar si la sesión sigue activa: 200 con el correo, o 401."""
    return {"email": admin.email}


@router.get("/sections", response_model=list[SectionOut])
def list_sections(_: Admin = Depends(current_admin), db: Session = Depends(get_db)):
    """Incluye también las secciones ocultas."""
    ensure_required_sections(db)
    return db.query(Section).order_by(Section.position).all()


RESERVED_KEYS = REQUIRED_KEYS | {"inicio", "admin"}


@router.post("/sections", response_model=SectionOut, status_code=201)
async def create_section(
    data: SectionCreate, request: Request, admin: Admin = Depends(current_admin), db: Session = Depends(get_db)
):
    if data.key in RESERVED_KEYS:
        raise HTTPException(422, f"La clave «{data.key}» está reservada")
    if db.get(Section, data.key):
        raise HTTPException(409, "Ya existe una sección con esa clave")
    position = data.position
    if position is None:
        position = (db.query(func.max(Section.position)).scalar() or 0) + 1
    section = Section(key=data.key, title=data.title, content=data.content, visible=data.visible, position=position)
    db.add(section)
    log_activity(
        db,
        request,
        admin.email,
        "section_create",
        f"Creó la sección «{data.key}»",
        "section",
        data.key,
        {"title": data.title, "visible": data.visible, "position": position},
    )
    db.commit()
    db.refresh(section)
    await hub.broadcast(
        {"event": "section_updated", "data": public_section(SectionOut.model_validate(section).model_dump(mode="json"))}
    )
    return section


@router.delete("/sections/{key}", status_code=204)
async def delete_section(
    key: str, request: Request, admin: Admin = Depends(current_admin), db: Session = Depends(get_db)
):
    if key in REQUIRED_KEYS:
        raise HTTPException(403, "Esta sección es obligatoria y no se puede borrar")
    section = db.get(Section, key)
    if not section:
        raise HTTPException(404, "Sección no existe")
    log_activity(
        db,
        request,
        admin.email,
        "section_delete",
        f"Eliminó la sección «{key}»",
        "section",
        key,
        {"title": section.title},
    )
    db.delete(section)
    db.commit()
    await hub.broadcast({"event": "section_deleted", "data": {"key": key}})


@router.put("/sections/{key}", response_model=SectionOut)
async def update_section(
    key: str,
    data: SectionUpdate,
    request: Request,
    admin: Admin = Depends(current_admin),
    db: Session = Depends(get_db),
):
    section = db.get(Section, key)
    if not section:
        raise HTTPException(404, "Sección no existe")
    changes = data.model_dump(exclude_unset=True)
    if key in REQUIRED_KEYS and changes.get("visible") is False:
        raise HTTPException(403, "Esta sección es obligatoria y no se puede ocultar")
    news_summary: dict = {}
    if key == "noticias" and changes.get("content") is not None:
        changes["content"], news_summary = apply_news_rules(section.content or {}, changes["content"])
    if key == "settings" and changes.get("content") is not None:
        changes["content"] = validate_menu(changes["content"])
    diff = section_changes(section, changes)  # antes de aplicar, para poder comparar
    if diff and news_summary:
        diff["news"] = news_summary  # qué noticias se crearon, editaron, activaron o desactivaron
    for field, value in changes.items():
        setattr(section, field, value)
    if diff:  # un guardado sin cambios reales no ensucia la bitácora
        log_activity(db, request, admin.email, "section_update", section_summary(key, diff), "section", key, diff)
    db.commit()
    db.refresh(section)
    # Los visitantes reciben la sección sin las noticias desactivadas
    await hub.broadcast(
        {"event": "section_updated", "data": public_section(SectionOut.model_validate(section).model_dump(mode="json"))}
    )
    return section


@router.post("/upload")
def upload(
    request: Request,
    file: UploadFile = File(...),
    admin: Admin = Depends(current_admin),
    db: Session = Depends(get_db),
):
    ext = ALLOWED.get(file.content_type or "")
    if not ext:
        raise HTTPException(400, "Solo png, jpg o webp")
    content = file.file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(400, "Máximo 5 MB")
    UPLOADS.mkdir(exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    (UPLOADS / name).write_bytes(content)
    url = f"/uploads/{name}"
    log_activity(
        db,
        request,
        admin.email,
        "upload",
        f"Subió la imagen «{(file.filename or name)[:80]}»",
        "file",
        url,
        {"original_name": (file.filename or "")[:200], "content_type": file.content_type, "bytes": len(content)},
    )
    db.commit()
    return {"url": url}


@router.get("/contacts", response_model=list[ContactOut])
def contacts(_: Admin = Depends(current_admin), db: Session = Depends(get_db)):
    return db.query(ContactMessage).order_by(ContactMessage.created_at.desc()).all()


@router.patch("/contacts/{contact_id}/read", response_model=ContactOut)
def mark_read(contact_id: int, request: Request, admin: Admin = Depends(current_admin), db: Session = Depends(get_db)):
    msg = db.get(ContactMessage, contact_id)
    if not msg:
        raise HTTPException(404, "Mensaje no existe")
    if not msg.read:  # releerlo no genera otro registro
        msg.read = True
        log_activity(
            db,
            request,
            admin.email,
            "contact_read",
            f"Marcó como leído el mensaje de {msg.name}",
            "contact",
            str(contact_id),
        )
    db.commit()
    db.refresh(msg)
    return msg


@router.delete("/contacts/{contact_id}", status_code=204)
def delete_contact(
    contact_id: int, request: Request, admin: Admin = Depends(current_admin), db: Session = Depends(get_db)
):
    msg = db.get(ContactMessage, contact_id)
    if msg:
        log_activity(
            db,
            request,
            admin.email,
            "contact_delete",
            f"Eliminó el mensaje de {msg.name}",
            "contact",
            str(contact_id),
            {"name": msg.name, "email": msg.email},
        )
        db.delete(msg)
        db.commit()


@router.get("/activity", response_model=ActivityPage)
def activity(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = None,
    entity_type: str | None = None,
    entity_key: str | None = None,
    admin_email: str | None = None,
    _: Admin = Depends(current_admin),
    db: Session = Depends(get_db),
):
    """Bitácora del administrador, de lo más reciente a lo más antiguo. Todos los filtros son opcionales."""
    query = db.query(ActivityLog)
    for column, value in (
        (ActivityLog.action, action),
        (ActivityLog.entity_type, entity_type),
        (ActivityLog.entity_key, entity_key),
        (ActivityLog.admin_email, admin_email),
    ):
        if value:
            query = query.filter(column == value)
    total = query.count()
    items = query.order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc()).offset(offset).limit(limit).all()
    return {"total": total, "items": items}
