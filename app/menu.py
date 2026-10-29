from fastapi import HTTPException

MAX_MENU_ITEMS = 10


def validate_menu(content: dict) -> dict:
    """Valida el menú de la sección «settings»: debe ser una lista de, como máximo, MAX_MENU_ITEMS enlaces.

    Si el contenido no trae `menu` no hay nada que validar.
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
    return content
