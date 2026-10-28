from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

# SQLite (pruebas) necesita check_same_thread; PostgreSQL falla en 5 s si no hay servidor, en vez de esperar minutos
connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {"connect_timeout": 5}
)
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
