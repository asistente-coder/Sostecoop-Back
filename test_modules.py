"""Límite de módulos, arranque que no recrea lo borrado y script eliminar_modulos.py.
Usa base temporal: DATABASE_URL=sqlite:///./test_tmp.db python test_modules.py"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import StaticPool, create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base
from app.main import app
from app.models import Section
from app.seed import MAX_MODULES, REQUIRED_KEYS, seed

assert MAX_MODULES == 7 and REQUIRED_KEYS == {"settings", "hero", "nosotros", "noticias", "contacto"}
tag = uuid4().hex[:6]

# 1) límite de módulos por la API (las obligatorias no cuentan)
with TestClient(app, headers={"Origin": "http://localhost:3000"}) as c:
    assert (
        c.post(
            "/api/admin/login", json={"email": settings.admin_email, "password": settings.admin_password}
        ).status_code
        == 200
    )

    def modules():
        return [s["key"] for s in c.get("/api/admin/sections").json() if s["key"] not in REQUIRED_KEYS]

    def create(key):
        return c.post("/api/admin/sections", json={"key": key, "title": f"Módulo {key}"})

    creados = []
    while len(modules()) < MAX_MODULES:
        key = f"mod-{tag}-{len(creados)}"
        assert create(key).status_code == 201
        creados.append(key)
    assert len(modules()) == MAX_MODULES

    r = create(f"mod-{tag}-extra")
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert f"máximo de {MAX_MODULES} módulos" in detail and "no cuentan" in detail and "settings" in detail, detail
    assert len(modules()) == MAX_MODULES  # el rechazo no creó nada
    assert create(modules()[0]).status_code == 409  # una clave repetida sigue dando 409
    assert create("hero").status_code == 422  # y una reservada, 422
    assert "reservada" in create("hero").json()["detail"]

    # al borrar uno hay lugar para otro; las obligatorias siguen sin poder borrarse
    libre = creados[0] if creados else modules()[-1]
    assert c.delete(f"/api/admin/sections/{libre}").status_code == 204
    assert create(f"mod-{tag}-nuevo").status_code == 201
    assert create(f"mod-{tag}-otro").status_code == 422
    assert c.delete("/api/admin/sections/contacto").status_code == 403
    creados = [k for k in creados if k != libre] + [f"mod-{tag}-nuevo"]
    for key in creados:  # deja la base como estaba
        assert c.delete(f"/api/admin/sections/{key}").status_code == 204

# 2) el arranque no recrea los módulos borrados, pero sí las secciones obligatorias
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(engine)
with sessionmaker(bind=engine)() as db:
    keys = lambda: {s.key for s in db.query(Section)}
    seed(db)
    assert len(keys()) == 9 and {"servicios", "beneficios", "testimonios", "faq"} <= keys()
    for k in ("faq", "testimonios"):
        db.delete(db.get(Section, k))
    db.commit()
    seed(db)  # «reinicio»
    assert not ({"faq", "testimonios"} & keys()) and len(keys()) == 7  # no reaparecen
    db.delete(db.get(Section, "noticias"))
    db.get(Section, "hero").visible = False
    db.commit()
    seed(db)
    assert "noticias" in keys() and db.get(Section, "hero").visible is True  # las obligatorias sí vuelven
    assert not ({"faq", "testimonios"} & keys())

# 3) script eliminar_modulos.py sobre una base temporal con los 12 módulos del pedido
ELIMINAR = [
    "Canales digitales",
    "Seguridad digital",
    "Convenios para asociados",
    "Bienestar cooperativo",
    "Participación cooperativa",
]
CONSERVAR = [
    "Servicios",
    "Beneficios",
    "Testimonios",
    "Preguntas frecuentes",
    "Ahorro programado",
    "Crédito responsable",
    "Educación financiera",
]
root = os.getcwd()
with tempfile.TemporaryDirectory() as tmp:
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{Path(tmp, 'modulos.db').as_posix()}",
        "PYTHONPATH": root,
        "PYTHONIOENCODING": "utf-8",
    }

    def run(*args, code=None):
        cmd = [sys.executable, "-W", "ignore"] + (
            ["-c", code] if code else [str(Path(root, "eliminar_modulos.py")), *args]
        )
        r = subprocess.run(cmd, env=env, cwd=tmp, capture_output=True, text=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr[-600:]
        return r.stdout

    preparar = """
import json
from app.database import Base, SessionLocal, engine
from app.models import Section
from app.seed import seed
Base.metadata.create_all(engine)
with SessionLocal() as db:
    seed(db)                                     # base nueva: 9 secciones (4 módulos: servicios, beneficios, testimonios, faq)
    titulos = %s
    for i, t in enumerate(titulos):
        key = t.lower().replace(' ', '-').replace('é', 'e').replace('ó', 'o').replace('á', 'a')
        db.add(Section(key=key, title=t, content={}, position=20 + i))
    settings = db.get(Section, 'settings')
    menu = list(settings.content['menu'])
    if not any(m['anchor'] == '#noticias' for m in menu):   # como el menú real: las 4 entradas obligatorias
        menu.append({'label': 'Noticias', 'anchor': '#noticias'})
    menu.insert(2, {'label': 'Canales digitales', 'anchor': '#canales-digitales'})
    menu.append({'label': 'Seguridad', 'anchor': '#seguridad-digital'})
    settings.content = {**settings.content, 'menu': menu}
    db.commit()
""" % json.dumps(ELIMINAR + ["Ahorro programado", "Crédito responsable", "Educación financiera"], ensure_ascii=False)
    run(code=preparar)

    def estado():
        out = run(
            code="""
import json
from app.database import SessionLocal
from app.models import Section, ActivityLog
from app.seed import REQUIRED_KEYS
with SessionLocal() as db:
    mods = [s.title for s in db.query(Section) if s.key not in REQUIRED_KEYS]
    menu = [m['anchor'] for m in db.get(Section, 'settings').content['menu']]
    print(json.dumps({'mods': mods, 'menu': menu, 'borrados': db.query(ActivityLog).filter(ActivityLog.action == 'section_delete').count()}, ensure_ascii=False))
"""
        )
        return json.loads(out.strip().splitlines()[-1])

    antes = estado()
    assert len(antes["mods"]) == 12 and "#canales-digitales" in antes["menu"], antes  # los 12 módulos del pedido

    # simulación: no cambia nada
    sim = run()
    assert "SIMULACIÓN" in sim and "Canales digitales" in sim and "#canales-digitales" in sim, sim
    assert estado() == antes and not Path(tmp, "backups").exists()

    # aplicar: respaldo, menú limpio y módulos borrados
    out = run("--aplicar", "--sin-preguntar")
    despues = estado()
    assert "Listo: 5 módulo(s) eliminados y 2 enlace(s)" in out, out
    assert sorted(despues["mods"]) == sorted(CONSERVAR), despues["mods"]
    assert len(despues["mods"]) == MAX_MODULES
    assert not [a for a in despues["menu"] if a in ("#canales-digitales", "#seguridad-digital")]
    assert all(
        a in despues["menu"] for a in ("#inicio", "#nosotros", "#noticias", "#contacto")
    )  # entradas obligatorias
    assert set(despues["menu"]) == set(antes["menu"]) - {
        "#canales-digitales",
        "#seguridad-digital",
    }  # solo se quitaron esos
    assert despues["menu"].index("#inicio") < despues["menu"].index("#nosotros")  # y el orden se conserva
    assert despues["borrados"] == antes["borrados"] + 5  # cada módulo eliminado queda en la bitácora
    assert len(list(Path(tmp, "backups").glob("secciones_antes_de_eliminar_modulos_*.json"))) == 1

    # repetirlo no cambia nada, y un reinicio (seed) no recrea los módulos eliminados
    assert "No hay módulos para eliminar" in run()
    run(code="from app.database import SessionLocal\nfrom app.seed import seed\nwith SessionLocal() as db: seed(db)\n")
    assert estado()["mods"] == despues["mods"]
print("MODULOS OK")
