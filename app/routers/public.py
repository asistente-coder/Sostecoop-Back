from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ContactMessage, Section
from ..news import public_news, public_section
from ..realtime import hub
from ..schemas import ContactIn, SectionOut
from ..seed import ensure_required_sections

router = APIRouter(prefix="/api/public", tags=["Público"])


@router.get("/content", response_model=list[SectionOut])
def content(db: Session = Depends(get_db)):
    """Las secciones visibles, ordenadas: la carga inicial de la web. No incluye las noticias desactivadas."""
    ensure_required_sections(db)  # las obligatorias nunca faltan en la respuesta pública
    sections = db.query(Section).filter(Section.visible.is_(True)).order_by(Section.position).all()
    return [public_section(SectionOut.model_validate(s).model_dump(mode="json")) for s in sections]


@router.get("/news/{slug}")
def news_by_slug(slug: str, db: Session = Depends(get_db)):
    """Una noticia por su slug. Si está desactivada responde igual que si no existiera (404)."""
    section = db.get(Section, "noticias")
    items = public_news(section.content or {}).get("items", []) if section else []
    for item in items:
        if isinstance(item, dict) and item.get("slug") == slug:
            return item
    raise HTTPException(404, "Noticia no existe")


@router.post("/contact", status_code=201)
async def contact(data: ContactIn, db: Session = Depends(get_db)):
    msg = ContactMessage(**data.model_dump())
    db.add(msg)
    db.commit()
    await hub.broadcast({"event": "new_contact", "data": {"id": msg.id}})
    return {"ok": True}


@router.websocket("/ws")
async def ws(websocket: WebSocket):
    """Los clientes escuchan aquí los cambios del admin en vivo."""
    await hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # mantiene viva la conexión (ping)
    except WebSocketDisconnect:
        hub.disconnect(websocket)
