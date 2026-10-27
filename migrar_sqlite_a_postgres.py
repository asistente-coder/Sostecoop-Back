"""Copia los datos de cooperativa.db (SQLite) a la base PostgreSQL de DATABASE_URL.

Uso (con .env ya apuntando a PostgreSQL):
    python migrar_sqlite_a_postgres.py            # origen: ./cooperativa.db
    python migrar_sqlite_a_postgres.py otra.db    # origen distinto

No borra nada: se detiene si la base de destino ya tiene secciones.
"""

import sys

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.database import Base, engine
from app.models import Admin, ContactMessage, Section

if engine.dialect.name != "postgresql":
    sys.exit(f"DATABASE_URL no apunta a PostgreSQL ({engine.dialect.name}). Revisa el archivo .env")

origen = sys.argv[1] if len(sys.argv) > 1 else "cooperativa.db"
src_engine = create_engine(f"sqlite:///{origen}")

Base.metadata.create_all(engine)

with Session(src_engine) as src, Session(engine) as dst:
    if dst.query(Section).count():
        sys.exit("El destino ya tiene datos. No se copió nada.")

    def copiar(modelo):
        filas = src.query(modelo).all()
        columnas = [c.name for c in modelo.__table__.columns]
        for f in filas:
            dst.add(modelo(**{c: getattr(f, c) for c in columnas}))
        print(f"{modelo.__tablename__}: {len(filas)} filas")

    for modelo in (Admin, Section, ContactMessage):
        copiar(modelo)
    dst.flush()
    # Los ids se copiaron tal cual: alinea los contadores automáticos de PostgreSQL
    for tabla in ("admins", "contact_messages"):
        dst.execute(
            text(f"SELECT setval(pg_get_serial_sequence('{tabla}', 'id'), COALESCE((SELECT MAX(id) FROM {tabla}), 1))")
        )
    dst.commit()

print("Listo: datos copiados a", engine.url.render_as_string(hide_password=True))
