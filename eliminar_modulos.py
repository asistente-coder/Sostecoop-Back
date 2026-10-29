"""Elimina módulos de la base configurada en DATABASE_URL, quitando antes sus enlaces del menú.

Uso (con el entorno virtual activado, en la carpeta del proyecto):
    python eliminar_modulos.py            simulación: muestra qué haría y no cambia nada
    python eliminar_modulos.py --aplicar  lo hace de verdad (guarda antes un respaldo en backups/)

Solo borra los módulos de ELIMINAR. Nunca toca las secciones obligatorias ni los demás módulos, y los módulos que ya no
existen se ignoran, así que se puede repetir sin problema.
"""

import argparse
import json
import unicodedata
from datetime import datetime
from pathlib import Path

from app.database import SessionLocal, engine
from app.models import ActivityLog, Section
from app.seed import MAX_MODULES, REQUIRED_KEYS

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
MENU_OBLIGATORIO = ["#inicio", "#nosotros", "#noticias", "#contacto"]


def norm(text: str) -> str:
    """Compara títulos sin tildes, mayúsculas ni espacios de más."""
    plain = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return " ".join(plain.split()).casefold()


def main() -> None:
    parser = argparse.ArgumentParser(description="Elimina módulos y sus enlaces del menú.")
    parser.add_argument("--aplicar", action="store_true", help="hacer los cambios (sin esto solo se simula)")
    parser.add_argument("--sin-preguntar", action="store_true", help="no pedir confirmación con --aplicar")
    args = parser.parse_args()

    print("Base:", engine.url.render_as_string(hide_password=True))
    with SessionLocal() as db:
        sections = db.query(Section).order_by(Section.position, Section.key).all()
        by_title = {norm(s.title): s for s in sections}

        targets, missing = [], []
        for title in ELIMINAR:
            section = by_title.get(norm(title))
            if section is None:
                missing.append(title)
            elif section.key in REQUIRED_KEYS:
                print(f"  OMITIDO «{title}»: es una sección obligatoria y no se puede eliminar")
            else:
                targets.append(section)

        settings = next((s for s in sections if s.key == "settings"), None)
        menu = list((settings.content or {}).get("menu", [])) if settings else []
        target_anchors = {f"#{s.key}" for s in targets}
        removed_links = [link for link in menu if str(link.get("anchor", "")).strip().casefold() in target_anchors]
        new_menu = [link for link in menu if link not in removed_links]

        print("\nSe eliminarán estos módulos:" if targets else "\nNo hay módulos para eliminar.")
        for s in targets:
            print(f"  - {s.title} ({s.key})")
        if missing:
            print("Ya no existen (se ignoran):", ", ".join(missing))
        print(
            "Enlaces del menú que se quitan:",
            [(link.get("label"), link.get("anchor")) for link in removed_links] or "ninguno",
        )

        remaining = [s for s in sections if s.key not in REQUIRED_KEYS and s not in targets]
        print(f"\nMódulos que quedan: {len(remaining)} (máximo {MAX_MODULES})")
        for s in remaining:
            print(f"  - {s.title}")
        not_found = [t for t in CONSERVAR if norm(t) not in {norm(s.title) for s in remaining}]
        if not_found:
            print("Aviso: no existen en esta base (no se crean):", ", ".join(not_found))
        extra = [s.title for s in remaining if norm(s.title) not in {norm(t) for t in CONSERVAR}]
        if extra:
            print("Aviso: hay módulos que no están en la lista a conservar (no se tocan):", ", ".join(extra))
        if len(remaining) > MAX_MODULES:
            print(f"Aviso: seguirían quedando más de {MAX_MODULES} módulos; hay que eliminar otros a mano.")
        anchors = {str(link.get("anchor", "")).strip().casefold() for link in new_menu}
        lacking = [a for a in MENU_OBLIGATORIO if a not in anchors]
        if lacking:
            print("Aviso: al menú le faltan entradas obligatorias (no se agregan aquí):", ", ".join(lacking))

        if not targets:
            return
        if not args.aplicar:
            print("\nSIMULACIÓN: no se cambió nada. Para hacerlo, ejecuta de nuevo con --aplicar")
            return
        if not args.sin_preguntar and input("\n¿Continuar? Escribe SI para eliminar: ").strip().upper() != "SI":
            print("Cancelado: no se cambió nada.")
            return

        backup = Path("backups")
        backup.mkdir(exist_ok=True)
        path = backup / f"secciones_antes_de_eliminar_modulos_{datetime.now():%Y%m%d_%H%M%S}.json"
        rows = [
            {"key": s.key, "title": s.title, "visible": s.visible, "position": s.position, "content": s.content}
            for s in sections
        ]
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print("\nRespaldo:", path)

        origin = {"origin": "eliminar_modulos.py"}
        if settings and removed_links:  # primero el menú, después los módulos
            settings.content = {**settings.content, "menu": new_menu}
            db.add(
                ActivityLog(
                    action="section_update",
                    entity_type="section",
                    entity_key="settings",
                    summary="Quitó del menú los enlaces de los módulos eliminados",
                    details={**origin, "removed_links": [link.get("anchor") for link in removed_links]},
                )
            )
        for s in targets:
            db.add(
                ActivityLog(
                    action="section_delete",
                    entity_type="section",
                    entity_key=s.key,
                    summary=f"Eliminó la sección «{s.key}»",
                    details={**origin, "title": s.title},
                )
            )
            db.delete(s)
        db.commit()
        print(f"Listo: {len(targets)} módulo(s) eliminados y {len(removed_links)} enlace(s) del menú quitados.")


if __name__ == "__main__":
    main()
