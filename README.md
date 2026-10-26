# Backend – Plataforma Cooperativa de Ahorro (FastAPI)

Un solo backend con dos "caras":

| Cara | URL del frontend | Quién | Qué hace |
|------|------------------|-------|----------|
| **Pública** | `/` | Cualquier visitante | Ve la página (solo lectura) y envía el formulario de contacto |
| **Admin** | `/admin` | Administrador (login) | Edita textos, imágenes, orden y visibilidad de las secciones |

Los cambios del admin se guardan y se **empujan en vivo por WebSocket** a todos los visitantes conectados, sin recargar.

## Arrancar

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- Documentación interactiva: http://localhost:8000/docs
- Al primer arranque se crea `cooperativa.db` (SQLite), el admin y las secciones iniciales.
- Credenciales iniciales: las de `.env` (`ADMIN_EMAIL` / `ADMIN_PASSWORD`). **Cambiarlas antes de publicar**, igual que `SECRET_KEY`.
- Prueba rápida: `pip install -r requirements-dev.txt` y `python test_smoke.py`.

## Estructura

```
app/
  main.py        app, CORS, archivos subidos
  config.py      variables de .env
  models.py      Admin, Section, ContactMessage
  routers/public.py   /api/public/*  (sin login + WebSocket)
  routers/admin.py    /api/admin/*   (JWT)
  realtime.py    reparte los cambios a los WebSockets
  seed.py        secciones iniciales (editar según Figma)
```

## Endpoints

Públicos:
- `GET  /api/public/content` → lista de secciones visibles
- `POST /api/public/contact` → `{name, email, phone?, message}`
- `WS   /api/public/ws` → eventos en vivo

Admin (header `Authorization: Bearer <token>`):
- `POST  /api/admin/login` → `{email, password}` → `{access_token}`
- `GET   /api/admin/me`
- `GET   /api/admin/sections` (incluye ocultas)
- `PUT   /api/admin/sections/{key}` → `{title?, content?, visible?, position?}` (parcial)
- `POST  /api/admin/upload` (multipart `file`, png/jpg/webp, máx 5 MB) → `{url}`
- `GET   /api/admin/contacts` · `PATCH /api/admin/contacts/{id}/read` · `DELETE /api/admin/contacts/{id}`

Las imágenes subidas se sirven en `http://localhost:8000/uploads/<archivo>`.

## Notas / pendientes

- No pude entrar al Figma (pide iniciar sesión), así que las secciones de `app/seed.py` son una propuesta genérica
  (settings, hero, nosotros, servicios, beneficios, testimonios, faq, contacto). Cada sección guarda un JSON libre
  en `content`: si el diseño tiene otras secciones o campos, basta ajustar `seed.py` (borrar `cooperativa.db` para resembrar)
  o crear secciones nuevas; **no hace falta tocar el backend**.
- Para producción: poner `CORS_ORIGINS` con el dominio real, usar HTTPS (WebSocket `wss://`) y, si hay varios workers,
  cambiar `realtime.py` por Redis pub/sub (ahora el hub vive en memoria de un solo proceso).

## Sección «noticias»

`key = noticias`, con `content.items[]` (`slug`, `title`, `category`, `date`, `author`, `reading_minutes`, `summary`, `image_url`, `image_alt`, `body`).
El `PUT /api/admin/sections/noticias` responde **422** si falta el `title`, si la `date` no es `AAAA-MM-DD` o si dos slugs se repiten.
Si el `slug` viene vacío se genera desde el título (minúsculas, sin tildes, con guiones; si choca, se añade `-2`, `-3`...).
Al arrancar, el servidor crea las secciones que falten en bases ya existentes.

## Crear y borrar módulos (admin)

- `POST /api/admin/sections` `{key, title, visible?, position?, content?}` → 201. `key` = `^[a-z0-9-]{2,40}$`; 409 si existe; 422 si el formato es inválido o la clave es reservada (`settings, hero, nosotros, noticias, contacto, inicio, admin`). Sin `position`, va al final. Emite `section_updated`.
- `DELETE /api/admin/sections/{key}` → 204; 403 para `settings, hero, nosotros, noticias, contacto`; 404 si no existe. Emite `{"event":"section_deleted","data":{"key":"..."}}`.

## PostgreSQL

1. Crear la base (una sola vez): `CREATE DATABASE cooperativa;`
2. En `.env`: `DATABASE_URL=postgresql+psycopg://USUARIO:CLAVE@localhost:5433/cooperativa` (si la clave tiene símbolos como `@` o `#`, codificarlos: `@` → `%40`).
3. `pip install -r requirements.txt` y, para llevar lo que ya hay en SQLite: `python migrar_sqlite_a_postgres.py`.
4. Arrancar el servidor normalmente. Las tablas se crean solas.
