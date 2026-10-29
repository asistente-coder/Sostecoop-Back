from fastapi import HTTPException

MAX_MENU_ITEMS = 10


def _destination(anchor: object) -> str:
    """Forma en que se compara un destino: sin espacios, sin mayúsculas y sin «/» final (`/noticias/` = `/noticias`)."""
    text = str(anchor).strip().casefold()
    return text.rstrip("/") if len(text) > 1 else text


def validate_menu(content: dict) -> dict:
    """Valida el menú de la sección «settings»: una lista de, como máximo, MAX_MENU_ITEMS enlaces sin destinos repetidos.

    El destino de cada enlace es su `anchor`. Si el contenido no trae `menu` no hay nada que validar.
    """
    menu = content.get("menu")
    if menu is None:
        return content
    if not isinstance(menu, list):
        raise HTTPException(422, "settings.menu debe ser una lista de enlaces")
    if len(menu) > MAX_MENU_ITEMS:
        raise HTTPException(
            422,
            f"El menú admite como máximo {MAX_MENU_ITEMS} enlaces y se enviaron {len(menu)}. "
            f"Quita {len(menu) - MAX_MENU_ITEMS} para poder guardar.",
        )

    seen: dict[str, tuple[int, str]] = {}
    for n, link in enumerate(menu, start=1):
        if not isinstance(link, dict):
            raise HTTPException(422, f"Enlace {n} del menú: formato inválido")
        anchor = link.get("anchor")
        if anchor is None or not str(anchor).strip():
            continue
        label = str(link.get("label", "")).strip() or "sin nombre"
        destination = _destination(anchor)
        if destination in seen:
            first_n, first_label = seen[destination]
            raise HTTPException(
                422,
                f"El menú tiene el destino «{str(anchor).strip()}» repetido: enlace {first_n} («{first_label}») y "
                f"enlace {n} («{label}»). Cada destino solo puede aparecer una vez; quita uno de los dos.",
            )
        seen[destination] = (n, label)
    return content
