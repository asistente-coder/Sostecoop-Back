# Backend – Plataforma Cooperativa de Ahorro (FastAPI)

Un solo backend con dos "caras":

| Cara | Ruta | Quién | Qué hace |
|------|------|-------|----------|
| **Pública** | `/api/public/*` | Cualquier visitante | Lee el contenido (solo lectura) y envía el formulario de contacto |
| **Admin** | `/api/admin/*` | Administrador (login) | Edita textos, imágenes, orden y visibilidad de las secciones, y consulta la actividad |

Los cambios del admin se guardan y se **empujan en vivo por WebSocket** a todos los visitantes conectados, sin recargar.
El backend también sirve un panel y una página de prueba sencillos en `/admin` y `/`, útiles para comprobar la API sin frontend.

## Requisitos

- **Python 3.10 a 3.15, de 64 bits** (recomendado: 3.12 o 3.13, que son las más probadas). Las dependencias se instalan como
  paquetes ya compilados; con una versión de Python fuera de ese rango, o de 32 bits, `pip` intenta compilarlas y falla
  pidiendo `link.exe` / «Microsoft C++ Build Tools». Si pasa, instalar Python 3.12 o 3.13 y crear de nuevo el `.venv`.
- PostgreSQL (recomendado) o SQLite para pruebas rápidas.

## Arrancar

Windows (PowerShell), en la carpeta del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env        # y editar los valores
python -m uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8000
```

- `--host 0.0.0.0` hace el servidor accesible desde otros equipos de la red (por ejemplo, el frontend de un compañero).
- `--reload-dir app` evita que se reinicie por cambios en `.venv` o en `uploads/`.
- Documentación interactiva: http://localhost:8000/docs · Estado: http://localhost:8000/api/health
- Al primer arranque se crean las tablas, el admin y las secciones iniciales. Con el `.env.example` la base es SQLite
  (`cooperativa.db`); para PostgreSQL ver más abajo.
- Credenciales iniciales: las de `.env` (`ADMIN_EMAIL` / `ADMIN_PASSWORD`). **Cambiarlas antes de publicar**, igual que `SECRET_KEY`.

## Configuración (`.env`)

| Variable | Para qué sirve |
|----------|----------------|
| `SECRET_KEY` | Firma de la sesión. Si cambia, se cierran las sesiones abiertas |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Admin que se crea al primer arranque |
| `DATABASE_URL` | `sqlite:///./cooperativa.db` o `postgresql+psycopg://USUARIO:CLAVE@localhost:5433/cooperativa` |
| `CORS_ORIGINS` | Orígenes del frontend permitidos, separados por coma y escritos uno a uno (`http://localhost:3000`, `http://localhost:5173`, ...) |
| `TOKEN_MINUTES` | Duración de la sesión y de la cookie (480 = 8 h, fija desde el login) |
| `ENVIRONMENT` | `production` marca la cookie como `Secure` (solo viaja por HTTPS) |

Después de cambiar el `.env`, reiniciar el servidor.

## Administrador y contraseña

**Cómo se crea.** No hay que ejecutar ningún comando: al arrancar, `seed()` (`app/seed.py`) crea el administrador con
`ADMIN_EMAIL` y `ADMIN_PASSWORD` del `.env`, pero **solo si la tabla `admins` está vacía**:

```python
if not db.query(Admin).first():
    db.add(Admin(email=settings.admin_email, password_hash=hash_password(settings.admin_password)))
```

La contraseña nunca se guarda en claro: `hash_password` (`app/security.py`) guarda `sal$hash`, con PBKDF2-HMAC-SHA256,
200 000 iteraciones y una sal aleatoria de 16 bytes. El login compara con `verify_password`.

**Cómo cambiarlos.** Editar `ADMIN_EMAIL` / `ADMIN_PASSWORD` en el `.env` **no** modifica un admin que ya existe. Para crear
un administrador nuevo o cambiar una contraseña se usa `crear_admin.py`, que pide la contraseña por teclado (mínimo 8
caracteres, no queda en el historial de la terminal):

```powershell
python crear_admin.py correo@ejemplo.com
```

- Si el correo ya existe, actualiza su contraseña; si no, crea un administrador nuevo (puede haber varios).
- Usa la base de `DATABASE_URL` del `.env`, así que se ejecuta en la carpeta del proyecto con el `.venv` activado.
- Las sesiones ya abiertas siguen siendo válidas hasta que venzan (`TOKEN_MINUTES`); para cerrarlas todas, cambiar `SECRET_KEY`.

### Crear otro administrador (paso a paso)

Puede haber varios administradores, cada uno con su correo y su contraseña, y todos entran por el mismo login. Todos tienen
los mismos permisos (no hay roles) y la bitácora guarda el correo de quien hizo cada cambio.

1. Abrir una terminal en la carpeta del proyecto y activar el entorno virtual:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

2. Ejecutar `crear_admin.py` con el correo del nuevo administrador (no hace falta detener el servidor):

   ```powershell
   python crear_admin.py nuevo.admin@ejemplo.com
   ```

3. Escribir la contraseña cuando la pida, y repetirla. No se ve mientras se escribe y debe tener mínimo 8 caracteres:

   ```
   Contraseña nueva:
   Repite la contraseña:
   ```

   Si todo sale bien, imprime `Administrador creado: nuevo.admin@ejemplo.com`.

4. Comprobar: entrar al login del admin con el correo y la contraseña nuevos, o consultar la tabla:

   ```sql
   SELECT id, email FROM admins ORDER BY id;
   ```

Notas:
- El correo es único: si ya existe, el script no crea otro, sino que **cambia la contraseña** de ese administrador
  (imprime `Contraseña actualizada para ...`).
- Escribe en la base de `DATABASE_URL` del `.env`. Si en esa terminal se definió antes `DATABASE_URL` para las pruebas,
  abrir una terminal nueva o ejecutar `Remove-Item Env:DATABASE_URL`; si no, el administrador se crea en la base temporal.
- Si se crea un administrador **antes del primer arranque del servidor**, el del `.env` ya no se crea, porque `seed()` solo
  lo hace cuando la tabla `admins` está vacía. Conviene arrancar el servidor una vez primero.

## Pruebas

Cada archivo se ejecuta solo y debe terminar con su mensaje de OK. Usan una base temporal, no tocan la real:

```powershell
$env:DATABASE_URL = "sqlite:///./test_tmp.db"
python test_smoke.py; python test_activity.py; python test_cookie.py
python test_sections.py; python test_required.py; python test_news.py
Remove-Item test_tmp.db
Remove-Item Env:DATABASE_URL    # vuelve a usar la base del .env
```

El último comando es importante: `$env:DATABASE_URL` sigue definido en esa terminal, y si luego se arranca el servidor o se crea un administrador ahí, se escribiría en la base temporal y no en la real.

## Estructura

```
app/
  main.py        app, CORS, archivos subidos, panel de prueba
  config.py      variables de .env
  models.py      Admin, Section, ContactMessage, ActivityLog
  security.py    contraseñas, JWT, cookie de sesión y chequeo anti-CSRF
  activity.py    registro de la actividad del admin
  news.py        validación de la sección «noticias»
  routers/public.py   /api/public/*  (sin login + WebSocket)
  routers/admin.py    /api/admin/*   (cookie de sesión)
  realtime.py    reparte los cambios a los WebSockets
  seed.py        secciones iniciales y secciones obligatorias
crear_admin.py                crea un administrador o cambia su contraseña
migrar_sqlite_a_postgres.py   pasa los datos de SQLite a PostgreSQL
```

## Endpoints

Públicos:
- `GET  /api/public/content` → lista de secciones visibles
- `POST /api/public/contact` → `{name, email, phone?, message}`
- `WS   /api/public/ws` → eventos en vivo

Admin (sesión en la cookie HttpOnly `sostecoop_admin`; el frontend envía las credenciales del navegador, sin `Authorization`;
las solicitudes que cambian datos validan el `Origin` contra `CORS_ORIGINS`):
- `POST  /api/admin/login` → `{email, password}` → `200 {"email"}` y `Set-Cookie` (HttpOnly, SameSite=Lax, Path=/, Max-Age = `TOKEN_MINUTES`, Secure si `ENVIRONMENT=production`)
- `POST  /api/admin/logout` → `204`, borra la cookie
- `GET   /api/admin/me` → `200 {"email"}` o `401`
- `GET   /api/admin/sections` (incluye ocultas)
- `PUT   /api/admin/sections/{key}` → `{title?, content?, visible?, position?}` (parcial)
- `POST  /api/admin/upload` (multipart `file`, png/jpg/webp, máx 5 MB) → `{url}`
- `GET   /api/admin/contacts` · `PATCH /api/admin/contacts/{id}/read` · `DELETE /api/admin/contacts/{id}`
- `GET   /api/admin/activity` → bitácora del admin (ver más abajo)

Las imágenes subidas se sirven en `/uploads/<archivo>`.

## Secciones

Cada sección guarda un JSON libre en `content`, así que añadir campos o secciones nuevas no requiere tocar el backend.
Las secciones iniciales (`app/seed.py`) son: `settings`, `hero`, `nosotros`, `servicios`, `beneficios`, `testimonios`, `faq`,
`contacto` y `noticias`.

**Obligatorias:** `settings`, `hero`, `nosotros`, `noticias` y `contacto` no se pueden borrar ni ocultar (`403`), y si faltan
en la base se recrean solas al listar o al pedir el contenido público.

### Sección «noticias»

`key = noticias`, con `content.items[]` (`slug`, `title`, `category`, `date`, `author`, `reading_minutes`, `summary`, `image_url`, `image_alt`, `body`).
El `PUT /api/admin/sections/noticias` responde **422** si falta el `title`, si la `date` no es `AAAA-MM-DD` o si dos slugs se repiten.
Si el `slug` viene vacío se genera desde el título (minúsculas, sin tildes, con guiones; si choca, se añade `-2`, `-3`...).

### Crear y borrar módulos (admin)

- `POST /api/admin/sections` `{key, title, visible?, position?, content?}` → 201. `key` = `^[a-z0-9-]{2,40}$`; 409 si existe; 422 si el formato es inválido o la clave es reservada (`settings, hero, nosotros, noticias, contacto, inicio, admin`). Sin `position`, va al final. Emite `section_updated`.
- `DELETE /api/admin/sections/{key}` → 204; 403 para las obligatorias; 404 si no existe. Emite `{"event":"section_deleted","data":{"key":"..."}}`.

## Actividad del admin

Cada acción queda en la tabla `activity_log`: quién (`admin_email`), qué (`action`), sobre qué (`entity_type` / `entity_key`),
una frase legible (`summary`), el detalle (`details`, JSON), la IP y la fecha. Se registra en la misma transacción que el cambio.

| `action` | Cuándo |
|----------|--------|
| `login`, `login_failed`, `logout` | Sesión (en el intento fallido se guarda el correo intentado, nunca la contraseña) |
| `section_create`, `section_update`, `section_delete` | Módulos; en la edición se guarda el antes y el después de `title`, `visible` y `position`, y los nombres de los campos de `content` que cambiaron |
| `upload` | Imagen subida (nombre original, tipo y tamaño) |
| `contact_read`, `contact_delete` | Mensajes de contacto |

No se registran los guardados sin cambios reales ni las solicitudes rechazadas por permisos o validación (por ejemplo, intentar borrar una sección obligatoria). Los intentos de login fallidos sí se registran.

`GET /api/admin/activity` → `{"total": N, "items": [...]}`, de lo más reciente a lo más antiguo.
Parámetros opcionales: `limit` (1–200, por defecto 50), `offset`, `action`, `entity_type`, `entity_key`, `admin_email`.

## Conectar un frontend

La cookie de sesión es `SameSite=Lax`: el navegador solo la envía si la página y la API son del **mismo sitio**. Por eso el
frontend debe llamar a rutas relativas (`/api/...`, `/uploads/...`) y un proxy las reenvía al backend; no debe usar la IP del
backend en el código. Ejemplo (Angular, `proxy.conf.json`):

```json
{
  "/api":     { "target": "http://localhost:8000", "secure": false, "changeOrigin": true, "ws": true },
  "/uploads": { "target": "http://localhost:8000", "secure": false, "changeOrigin": true }
}
```

- Cada origen desde el que se abra el frontend (por ejemplo `http://localhost:3000`) debe estar en `CORS_ORIGINS`; si no,
  el login responde `403`.
- Más detalles de integración, con ejemplos de peticiones: [FRONTEND.md](FRONTEND.md).

## PostgreSQL

1. Crear la base (una sola vez): `CREATE DATABASE cooperativa;`
2. En `.env`: `DATABASE_URL=postgresql+psycopg://USUARIO:CLAVE@localhost:5433/cooperativa` (si la clave tiene símbolos como `@` o `#`, codificarlos: `@` → `%40`).
3. Para llevar lo que ya hay en SQLite: `python migrar_sqlite_a_postgres.py`.
4. Arrancar el servidor normalmente. Las tablas se crean solas.

## Producción

- Poner `ENVIRONMENT=production` y servir todo por HTTPS (WebSocket `wss://`), con el sitio y la API bajo el mismo dominio.
- Cambiar `SECRET_KEY`, `ADMIN_PASSWORD` y poner en `CORS_ORIGINS` el dominio real.
- Si hay varios procesos, cambiar `realtime.py` por Redis pub/sub (ahora el hub vive en la memoria de un solo proceso).


