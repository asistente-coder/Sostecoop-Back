from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ContactMessage, Section
from ..realtime import hub
from ..schemas import ContactIn, SectionOut

router = APIRouter(prefix="/api/public", tags=["Público"])


@router.get("/content", response_model=list[SectionOut])
def content(db: Session = Depends(get_db)):
    """Todas las secciones visibles, ordenadas. Es la carga inicial de la web."""
    return db.query(Section).filter(Section.visible.is_(True)).order_by(Section.position).all()


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
