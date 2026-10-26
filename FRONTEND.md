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

1. **Login**: `POST /api/admin/login` `{email, password}` → `{access_token}`. `401` = credenciales mal.
   Guardar el token (memoria/`sessionStorage`) y mandarlo en todas las llamadas: `Authorization: Bearer <token>`.
   Si cualquier llamada devuelve `401` → borrar token y volver al login (el token dura 8 h).
   Proteger la ruta `/admin` con un guard (si no hay token, redirigir al login).
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

- **CORS**: el backend solo acepta los orígenes de `CORS_ORIGINS` (por defecto `localhost:5173` y `localhost:3000`). Si el front usa otro puerto/dominio, pedirlo.
- Fechas en ISO 8601 UTC.
- Errores: `{"detail": "mensaje"}` (o lista para `422`). Mostrar el `detail` al usuario.
- Credenciales de prueba de desarrollo: `admin@cooperativa.com` / `CambiaEsta123` (se cambiarán en producción).
- Accesibilidad/UX mínima: estados de carga, errores visibles, botón "Guardando…" y confirmación al guardar.

## 5. Checklist de entrega

- [ ] `/` renderiza el diseño de Figma con datos de `GET /content`
- [ ] Cambiar algo en `/admin` se ve en `/` (otra pestaña) sin recargar
- [ ] Reconexión automática del WebSocket
- [ ] Formulario de contacto con validación y mensajes de éxito/error
- [ ] Login, logout y guard de `/admin`
- [ ] Subida de imágenes y vista previa en el editor
- [ ] Responsive (móvil/tablet/desktop) como en Figma
