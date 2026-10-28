# Guía para el Frontend

API base en desarrollo: `http://localhost:8000` (Swagger con todo: `/docs`).
Configurar como variable de entorno, p. ej. `VITE_API_URL=http://localhost:8000`.

## 1. Qué hay que construir: 2 rutas

| Ruta | Descripción |
|------|-------------|
| `/` | **Sitio público**: es el diseño de Figma, pero sus textos/imágenes vienen de la API, no hardcodeados. |
| `/admin` | **Panel admin**: login + editor de las secciones + bandeja de mensajes de contacto. |

Recomendado: React (Vite) + React Router. Cualquier framework sirve.

## 2. Sitio público (`/`)

1. Al cargar: `GET /api/public/content` → array de secciones, ya ordenado y solo las visibles:
   ```json
   [{ "key": "hero", "title": "Inicio", "visible": true, "position": 1,
      "content": { "title": "...", "subtitle": "...", "cta_label": "...", "image_url": "" },
      "updated_at": "..." }]
   ```
   Guardar en un estado/store indexado por `key`. Renderizar cada componente del diseño con `content` de su `key`
   (`settings`, `hero`, `nosotros`, `servicios`, `beneficios`, `testimonios`, `faq`, `contacto`).
   Los campos exactos están en `app/seed.py`; si falta alguno, avisar al backend para añadirlo.
2. **Tiempo real**: abrir `new WebSocket("ws://localhost:8000/api/public/ws")` (en producción `wss://`).
   Eventos:
   - `{"event":"section_updated","data":<sección completa>}` → reemplazar esa `key` en el estado (si `visible=false`, quitarla; si es nueva, insertarla y reordenar por `position`).
   - `{"event":"new_contact", ...}` → lo ignora el público.
   Enviar un ping cada ~30 s (`ws.send("ping")`) y **reconectar automáticamente** si se cae (con backoff). Al reconectar, volver a llamar `GET /content`.
3. Imágenes: `image_url` que empiece por `/uploads/` se antepone con la URL de la API (`API_URL + image_url`). Si está vacío, usar la imagen del diseño por defecto.
4. **Formulario de contacto** (`#contacto`): `POST /api/public/contact`
   ```json
   { "name": "min 2", "email": "válido", "phone": "opcional", "message": "min 5, máx 3000" }
   ```
   `201` → mostrar "Mensaje enviado"; `422` → mostrar errores de validación por campo.
5. El menú/anclas (`#nosotros`, `#contacto`...) vienen en `settings.content.menu`.

## 3. Panel admin (`/admin`)

1. **Sesión por cookie** (ya no hay token en el frontend):
   - `POST /api/admin/login` `{email, password}` → `200 {"email": "..."}` y el navegador guarda la cookie `sostecoop_admin`
     (HttpOnly: el JS no la ve). `401` = credenciales mal.
   - **Todas** las llamadas a `/api/admin/*` deben ir con credenciales: `fetch(url, { credentials: "include" })`,
     o en Angular `withCredentials: true` (mejor con un interceptor). Ya no se envía `Authorization`.
   - `GET /api/admin/me` → `200 {"email": "..."}` si la sesión sigue activa, `401` si no. Úsalo para el guard de `/admin`
     al cargar la app.
   - `POST /api/admin/logout` → `204` y la cookie se borra.
   - Cualquier `401` → volver al login (la sesión dura 8 h).
   - **CSRF:** las llamadas POST/PUT/PATCH/DELETE se rechazan con `403` si el `Origin` del navegador no está en `CORS_ORIGINS`
     (el navegador lo envía solo; no hay que hacer nada).
   - **Importante (SameSite=Lax):** la cookie solo viaja si frontend y API están en el mismo *sitio*. `localhost:3000` → `localhost:8000`
     funciona (el puerto no cuenta), pero `localhost:3000` → `192.168.x.x:8000` NO. En desarrollo usa un proxy
     (en Angular, `proxy.conf.json`: `/api` → `http://IP:8000`, con `ws: true`) para que el navegador vea todo en el mismo origen.
2. **Lista de secciones**: `GET /api/admin/sections` (incluye ocultas). Mostrar una lista/pestañas por sección.
3. **Editor por sección**: formulario generado a partir de `content` (inputs de texto, textarea, y listas editables para `items` con agregar/quitar/ordenar).
   Guardar con `PUT /api/admin/sections/{key}` – es parcial, se pueden mandar solo los campos que cambian:
   ```json
   { "content": { ...el objeto content COMPLETO... }, "visible": true, "position": 2, "title": "..." }
   ```
   ⚠️ `content` se **reemplaza completo**: enviar todo el objeto, no solo el campo editado.
   Al guardar, los visitantes lo ven al instante (el backend hace el broadcast; el front público no hace nada extra).
4. **Imágenes**: `POST /api/admin/upload` (`multipart/form-data`, campo `file`; png/jpg/webp, máx 5 MB) → `{ "url": "/uploads/xxx.png" }`.
   Poner esa `url` en el campo `image_url` correspondiente y guardar la sección.
5. **Mostrar/ocultar y reordenar**: toggle de `visible` y `position` (drag & drop opcional) vía el mismo `PUT`.
6. **Mensajes de contacto**: `GET /api/admin/contacts` (más recientes primero), marcar leído `PATCH /api/admin/contacts/{id}/read`, borrar `DELETE /api/admin/contacts/{id}`.
   Opcional: también abrir el WebSocket en el admin y refrescar la bandeja al recibir `new_contact` (mostrar contador de no leídos).
7. Botón "Ver sitio" que abra `/` en otra pestaña para comprobar el cambio en vivo.

## 4. Detalles técnicos

- **CORS**: el backend solo acepta los orígenes listados en `CORS_ORIGINS` (por defecto `localhost:5173` y `localhost:3000`), con credenciales. Si el front usa otro puerto/dominio (p. ej. Angular en `http://localhost:4200`), hay que añadirlo.
- Fechas en ISO 8601 UTC.
- Errores: `{"detail": "mensaje"}` (o lista para `422`). Mostrar el `detail` al usuario.
- Credenciales de prueba de desarrollo: `admin.sostecoop@gmail.com` / `sostecoopltda` (se cambiarán en producción).
- Accesibilidad/UX mínima: estados de carga, errores visibles, botón "Guardando…" y confirmación al guardar.

## 5. Checklist de entrega

- [ ] `/` renderiza el diseño de Figma con datos de `GET /content`
- [ ] Cambiar algo en `/admin` se ve en `/` (otra pestaña) sin recargar
- [ ] Reconexión automática del WebSocket
- [ ] Formulario de contacto con validación y mensajes de éxito/error
- [ ] Login, logout y guard de `/admin`
- [ ] Subida de imágenes y vista previa en el editor
- [ ] Responsive (móvil/tablet/desktop) como en Figma
