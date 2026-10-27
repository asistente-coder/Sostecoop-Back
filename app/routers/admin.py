import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Admin, ContactMessage, Section
from ..news import validate_news
from ..realtime import hub
from ..schemas import ContactOut, LoginIn, SectionCreate, SectionOut, SectionUpdate, SessionOut
from ..security import (
    clear_session_cookie,
    create_token,
    csrf_protect,
    current_admin,
    set_session_cookie,
    verify_password,
)
from ..seed import REQUIRED_KEYS, ensure_required_sections

router = APIRouter(prefix="/api/admin", tags=["Admin"], dependencies=[Depends(csrf_protect)])
UPLOADS = Path("uploads")
ALLOWED = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
MAX_BYTES = 5 * 1024 * 1024
@router.post("/login", response_model=SessionOut)
def login(data: LoginIn, response: Response, db: Session = Depends(get_db)):
    """Valida las credenciales y guarda el JWT en la cookie HttpOnly `sostecoop_admin` (no va en el cuerpo)."""
    admin = db.query(Admin).filter(Admin.email == data.email).first()
    if not admin or not verify_password(data.password, admin.password_hash):
        raise HTTPException(401, "Credenciales incorrectas")
    set_session_cookie(response, create_token(admin.email))
    return {"email": admin.email}
@router.post("/logout", status_code=204)
def logout(response: Response):
    """Cierra la sesión borrando la cookie (mismos path, SameSite y Secure con los que se creó)."""
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
async def create_section(data: SectionCreate, _: Admin = Depends(current_admin), db: Session = Depends(get_db)):
    if data.key in RESERVED_KEYS:
        raise HTTPException(422, f"La clave «{data.key}» está reservada")
    if db.get(Section, data.key):
        raise HTTPException(409, "Ya existe una sección con esa clave")
    position = data.position
    if position is None:
        position = (db.query(func.max(Section.position)).scalar() or 0) + 1
    section = Section(key=data.key, title=data.title, content=data.content, visible=data.visible, position=position)
    db.add(section)
    db.commit()
    db.refresh(section)
    await hub.broadcast(
        {"event": "section_updated", "data": SectionOut.model_validate(section).model_dump(mode="json")}
    )
    return section
@router.delete("/sections/{key}", status_code=204)
async def delete_section(key: str, _: Admin = Depends(current_admin), db: Session = Depends(get_db)):
    if key in REQUIRED_KEYS:
        raise HTTPException(403, "Esta sección es obligatoria y no se puede borrar")
    section = db.get(Section, key)
    if not section:
        raise HTTPException(404, "Sección no existe")
    db.delete(section)
    db.commit()
    await hub.broadcast({"event": "section_deleted", "data": {"key": key}})
@router.put("/sections/{key}", response_model=SectionOut)
async def update_section(
    key: str, data: SectionUpdate, _: Admin = Depends(current_admin), db: Session = Depends(get_db)
):
    section = db.get(Section, key)
    if not section:
        raise HTTPException(404, "Sección no existe")
    changes = data.model_dump(exclude_unset=True)
    if key in REQUIRED_KEYS and changes.get("visible") is False:
        raise HTTPException(403, "Esta sección es obligatoria y no se puede ocultar")
    if key == "noticias" and changes.get("content") is not None:
        changes["content"] = validate_news(changes["content"])
    for field, value in changes.items():
        setattr(section, field, value)
    db.commit()
    db.refresh(section)
    await hub.broadcast(
        {"event": "section_updated", "data": SectionOut.model_validate(section).model_dump(mode="json")}
    )
    return section
@router.post("/upload")
def upload(file: UploadFile = File(...), _: Admin = Depends(current_admin)):
    ext = ALLOWED.get(file.content_type or "")
    if not ext:
        raise HTTPException(400, "Solo png, jpg o webp")
    content = file.file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(400, "Máximo 5 MB")
    UPLOADS.mkdir(exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    (UPLOADS / name).write_bytes(content)
    return {"url": f"/uploads/{name}"}
@router.get("/contacts", response_model=list[ContactOut])
def contacts(_: Admin = Depends(current_admin), db: Session = Depends(get_db)):
    return db.query(ContactMessage).order_by(ContactMessage.created_at.desc()).all()
@router.patch("/contacts/{contact_id}/read", response_model=ContactOut)
def mark_read(contact_id: int, _: Admin = Depends(current_admin), db: Session = Depends(get_db)):
    msg = db.get(ContactMessage, contact_id)
    if not msg:
        raise HTTPException(404, "Mensaje no existe")
    msg.read = True
    db.commit()
    db.refresh(msg)
    return msg
@router.delete("/contacts/{contact_id}", status_code=204)
def delete_contact(contact_id: int, _: Admin = Depends(current_admin), db: Session = Depends(get_db)):
    msg = db.get(ContactMessage, contact_id)
    if msg:
        db.delete(msg)
        db.commit()