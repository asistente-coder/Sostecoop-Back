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
- **PostgreSQL** (es la base de datos del proyecto), con la base `cooperativa` creada (ver «PostgreSQL» más abajo).

## Arrancar

Windows (PowerShell). Desde cero, tal como lo haría quien descarga el proyecto de GitHub:

```powershell
git clone https://github.com/asistente-coder/Sostecoop-Back.git
cd Sostecoop-Back
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8000
```

Antes de arrancar, PostgreSQL debe estar encendido y la base `cooperativa` creada (ver «PostgreSQL» más abajo).
**No hace falta crear un `.env`** si PostgreSQL está en `localhost:5432` con usuario `postgres` y contraseña `postgres`: son los
valores por defecto, junto con el administrador inicial de más abajo. Con otros datos de conexión (otro puerto o contraseña, por
ejemplo) sí hace falta el `.env`: se copia la plantilla y se edita `DATABASE_URL`. El archivo debe llamarse exactamente `.env`
(con el punto al inicio y sin nada después); `.env.example` es solo la plantilla y el programa no la lee:

```powershell
Copy-Item .env.example .env
```

Después se edita el `.env` y se reinicia el servidor. El `.env` no se sube a GitHub, porque puede tener claves.

- `--host 0.0.0.0` hace el servidor accesible desde otros equipos de la red (por ejemplo, el frontend de un compañero).
- `--reload-dir app` evita que se reinicie por cambios en `.venv` o en `uploads/`.
- Documentación interactiva: http://localhost:8000/docs · Estado: http://localhost:8000/api/health
- Al primer arranque se crean las tablas, el admin y las secciones iniciales. Si PostgreSQL no responde, el servidor se detiene
  en pocos segundos con un mensaje que indica a qué base intentó conectar.
- **Administrador inicial:** al primer arranque se crea solo, sin ejecutar nada más, con el correo `admin.sostecoop@gmail.com` y la
  contraseña `sostecoopltda` (o los de `ADMIN_EMAIL` / `ADMIN_PASSWORD` si están en el `.env`). **Cambiarlos antes de publicar**,
  igual que `SECRET_KEY`.

## Configuración (`.env`)

| Variable | Para qué sirve |
|----------|----------------|
| `SECRET_KEY` | Firma de la sesión. Si cambia, se cierran las sesiones abiertas |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Admin que se crea al primer arranque. Por defecto `admin.sostecoop@gmail.com` / `sostecoopltda` |
| `DATABASE_URL` | Por defecto `postgresql+psycopg://postgres:postgres@localhost:5432/cooperativa`. Para pruebas rápidas sin PostgreSQL: `sqlite:///./cooperativa.db` |
| `CORS_ORIGINS` | Orígenes del frontend permitidos, separados por coma y escritos uno a uno (`http://localhost:3000`, `http://localhost:5173`, ...) |
| `TOKEN_MINUTES` | Duración de la sesión y de la cookie (480 = 8 h, fija desde el login) |
| `NEWS_CREATED_AT_FALLBACK` | Opcional. Fecha ISO 8601 (`2026-10-01T00:00:00+00:00`) que se asigna como `created_at` a las noticias antiguas que no la tienen. Vacío = el momento de la migración |
| `ENVIRONMENT` | `production` marca la cookie como `Secure` (solo viaja por HTTPS) |

Después de cambiar el `.env`, reiniciar el servidor.

## Administrador y contraseña

**Cómo se crea.** No hay que ejecutar ningún comando: al correr `uvicorn` por primera vez, `seed()` (`app/seed.py`) crea el
administrador con `ADMIN_EMAIL` y `ADMIN_PASSWORD`, pero **solo si la tabla `admins` está vacía**. Si no existe un `.env` (o no
define esas variables), se usan los valores por defecto de `app/config.py`:

| Correo | Contraseña |
|--------|------------|
| `admin.sostecoop@gmail.com` | `sostecoopltda` |

El código que lo hace:

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
python test_menu.py; python test_news_rules.py; python test_news_categories.py
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
  menu.py        validación del menú de «settings» (máximo de enlaces)
  routers/public.py   /api/public/*  (sin login + WebSocket)
  routers/admin.py    /api/admin/*   (cookie de sesión)
  realtime.py    reparte los cambios a los WebSockets
  seed.py        secciones iniciales y secciones obligatorias
crear_admin.py                crea un administrador o cambia su contraseña
migrar_sqlite_a_postgres.py   pasa los datos de SQLite a PostgreSQL
```

## Endpoints

Públicos:
- `GET  /api/public/content` → lista de secciones visibles (en «noticias», solo las noticias activas)
- `GET  /api/public/news/{slug}` → una noticia activa; `404` si no existe o está desactivada
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

`key = noticias`, con `content.items[]`. Cada noticia tiene `slug`, `title`, `category`, `date`, `author`, `reading_minutes`,
`summary`, `image_url`, `image_alt`, `body` y tres campos que maneja el servidor:

| Campo | Qué es |
|-------|--------|
| `id` | Identificador estable (texto de 32 caracteres) que asigna el servidor. Con él se reconoce cada noticia al guardar |
| `created_at` | Fecha y hora UTC de creación (ISO 8601), puesta por el servidor. **Inmutable**: lo que mande el frontend se ignora |
| `active` | `true` o `false`. Una noticia nueva siempre nace con `true` |

El `PUT /api/admin/sections/noticias` recibe **la lista completa**: las noticias que ya existen, tal como llegaron (con su `id`),
más las nuevas **sin** `id`. Responde **422** (`{"detail": "..."}`) en estos casos:

- Falta el `title`, la `date` no es `AAAA-MM-DD` o dos slugs se repiten. Si el `slug` viene vacío se genera desde el título
  (minúsculas, sin tildes, con guiones; si choca, se añade `-2`, `-3`...).
- **No se puede borrar ni quitar una noticia de la lista.** Para ocultarla al público se desactiva con `active: false`.
  Tampoco se puede borrar la sección (`DELETE` responde `403`).
- Llega un `id` que no existe o repetido, o un `active` que no es booleano. Las noticias nuevas se envían sin `id`.
- **Ventana de edición de 72 horas:** el contenido (todo menos `id`, `created_at` y `active`) solo se puede cambiar durante las
  72 horas siguientes a `created_at`. Pasado ese plazo, cualquier cambio de contenido se rechaza. La `date` (fecha de publicación,
  editable) **no** cuenta para el plazo. Reordenar la lista sí está permitido.
- `active` se puede cambiar **en cualquier momento**, también después de las 72 horas: una noticia desactivada se puede reactivar.

#### Categorías de las noticias

`content.categories` es la lista de categorías disponibles, como lista de textos. Viaja en el mismo contenido de la sección, así
que se guarda con `PUT /api/admin/sections/noticias` y se devuelve en `GET /api/admin/sections`, en `GET /api/public/content` y en
los mensajes del WebSocket; no hay endpoints aparte. Cada noticia conserva su propio `category` (texto).

- Cada categoría debe ser un texto no vacío de **máximo 40 caracteres**. Se guardan sin espacios al inicio ni al final.
- **No puede haber repetidas**: al comparar se ignoran mayúsculas y espacios (`Ahorro`, ` ahorro ` y `AHORRO` son la misma).
  Las tildes sí cuentan (`Crédito` y `Credito` son distintas).
- Si el guardado **no trae** `categories` (o trae `null`), se conservan las que ya estaban: guardar otros campos no las borra.
  Enviar `[]` las quita todas, siempre que ninguna esté en uso.
- **No se puede eliminar una categoría que alguna noticia usa** (activa, desactivada o ya cerrada): 422 con el nombre de la
  categoría y de las noticias que la usan. Se evalúa el estado final de la petición, así que se puede reasignar una noticia y
  quitar la categoría en el mismo guardado. Una noticia cerrada (más de 72 horas) no puede cambiar de categoría.
- Una categoría nueva queda disponible para las noticias apenas se guarda, incluso en la misma petición que crea la noticia.
- El `category` de una noticia es texto libre: el servidor no exige que esté en la lista.
- Mensajes de error: `noticias.categories debe ser una lista de textos`, `Categoría 2: no puede estar vacía`,
  `Categoría 2: «…» tiene 41 caracteres (máximo 40)`, `Categoría 3: «ahorro» está repetida…` y
  `No se puede eliminar la categoría «X»: la usan 2 noticia(s) (…)`.
- La bitácora registra en `details.news` las categorías agregadas y quitadas (`categories_added`, `categories_removed`).

**Qué ve el público:** solo las noticias con `active: true`, tanto en `GET /api/public/content` como en
`GET /api/public/news/{slug}` y en los mensajes `section_updated` del WebSocket. El panel de administración
(`GET /api/admin/sections`) recibe todas, activas o no.

**Bitácora:** al guardar noticias, `details.news` indica cuáles se crearon, editaron, activaron o desactivaron.

#### Noticias existentes (migración)

Al arrancar, el servidor completa `id`, `active` y `created_at` en las noticias que no los tengan (es idempotente: si ya los
tienen, no cambia nada). Las noticias antiguas no guardan su fecha real de creación, y la `date` no se usa porque es editable,
así que reciben `NEWS_CREATED_AT_FALLBACK` o, si no está definida, el momento de la migración. Eso significa que **esas noticias
se pueden editar durante 72 horas contando desde la migración**. Para cerrarlas antes, se define `NEWS_CREATED_AT_FALLBACK` con
una fecha anterior. La migración queda registrada en la actividad como `news_migration`. No cambia el esquema de la base de
datos: las noticias siguen guardadas en el JSON de la sección `noticias`.

### Menú de «settings»

`settings.content.menu` es la lista de enlaces del menú de la página y admite **como máximo 10**. La regla se aplica en el
backend (`app/menu.py`), así que vale también para peticiones directas a la API, sin pasar por el frontend:

- `PUT /api/admin/sections/settings` con más de 10 enlaces → **422** `{"detail": "El menú admite como máximo 10 enlaces y se enviaron 11. Quita 1 para poder guardar."}`.
- Si `menu` no es una lista → **422** `settings.menu debe ser una lista de enlaces`.
- Un guardado rechazado no cambia nada: no se guarda, no se anuncia por WebSocket y no se registra en la actividad.
- Si el contenido no trae `menu`, no hay nada que validar. El límite está en `MAX_MENU_ITEMS` (`app/menu.py`).

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

PostgreSQL es la base de datos del proyecto. Pasos para dejarla lista:

1. Instalar PostgreSQL y dejarlo encendido. Anotar el usuario, la contraseña y el puerto (por defecto `postgres` y `5432`).
2. Crear la base, una sola vez (con `psql` o pgAdmin):

   ```powershell
   psql -U postgres -p 5432 -c "CREATE DATABASE cooperativa;"
   ```

3. Si los datos de conexión **no** son `postgres` / `postgres` / `5432`, crear el `.env` (`Copy-Item .env.example .env`) y poner en él:

   ```
   DATABASE_URL=postgresql+psycopg://USUARIO:CLAVE@localhost:PUERTO/cooperativa
   ```

   Si la clave tiene símbolos como `@` o `#`, hay que codificarlos: `@` → `%40`.
4. Arrancar el servidor normalmente. Las tablas, las secciones iniciales y el administrador se crean solos en esa base.
5. Si ya había datos en una base SQLite antigua y se quieren llevar a PostgreSQL: `python migrar_sqlite_a_postgres.py`.

## Producción

- Poner `ENVIRONMENT=production` y servir todo por HTTPS (WebSocket `wss://`), con el sitio y la API bajo el mismo dominio.
- Cambiar `SECRET_KEY`, `ADMIN_PASSWORD` y poner en `CORS_ORIGINS` el dominio real.
- Si hay varios procesos, cambiar `realtime.py` por Redis pub/sub (ahora el hub vive en la memoria de un solo proceso).


