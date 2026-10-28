"""Crea el administrador o cambia su contraseña.

Uso:  python crear_admin.py correo@ejemplo.com
La contraseña se pide por teclado (no queda en el historial de la terminal).
"""

import sys
from getpass import getpass

from app.database import Base, SessionLocal, engine
from app.models import Admin
from app.security import hash_password


def main() -> None:
    if len(sys.argv) != 2 or "@" not in sys.argv[1]:
        sys.exit("Uso: python crear_admin.py correo@ejemplo.com")
    email = sys.argv[1].strip()

    password = getpass("Contraseña nueva: ")
    if len(password) < 8:
        sys.exit("La contraseña debe tener al menos 8 caracteres.")
    if password != getpass("Repite la contraseña: "):
        sys.exit("Las contraseñas no coinciden.")

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        admin = db.query(Admin).filter(Admin.email == email).first()
        if admin:
            admin.password_hash = hash_password(password)
            print(f"Contraseña actualizada para {email}")
        else:
            db.add(Admin(email=email, password_hash=hash_password(password)))
            print(f"Administrador creado: {email}")
        db.commit()


if __name__ == "__main__":
    main()
