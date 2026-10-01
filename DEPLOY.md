# Despliegue a producción — Mayu Bodega (Render, plan free)

Este proyecto **no es igual** al de "API Estado de Bots". Ese proyecto tolera Render
gratuito porque los datos se auto-repueblan solos (los bots reportan cada rato).
Mayu Bodega guarda **negocio real**: inventario, ventas, deudas, clientes y fotos de
productos. En Render (plan free) el sistema de archivos **es efímero**: `db.sqlite3`
y `backend/media/` **se pierden en cada redeploy** y **nadie los repuebla solo**.

> **Recomendación fuerte:** si esto va a operar una bodega real, usa la sección
> [Alternativa persistente](#alternativa-persistente-recomendada). El flujo "free"
> de abajo solo tiene sentido para pruebas o si aceptas el ritual de respaldo.

---

## Diferencias clave vs. el proyecto de bots

| Aspecto | Bots | Mayu Bodega |
| --- | --- | --- |
| Datos | Reportados por los bots, se regeneran | Negocio real (BD + imágenes) |
| Almacenamiento | Solo `db.sqlite3` | `backend/db.sqlite3` **+** `backend/media/` |
| Backend | En la raíz | En `backend/` (requirements también ahí) |
| Auth | Header `X-API-Key` | Login + `Authorization: Token ...` |
| Datos iniciales | — | `seed_roles`, `seed_demo`, `seed_stock` |
| Frontend | Solo un dashboard | SPA completa (React Router) en la raíz |
| Tarea semanal | — | `sync_bcv_rate` (tasa BCV) |

---

## 1. Preparación del repo

Hoy el repo está en rama `main`, **sin remoto** y con muchos cambios sin
commitear. No hay `render.yaml`.

```powershell
cd "C:\Users\HellRaiser\Documents\Mayu Bodega"

# 1. Revisar y commitear el trabajo pendiente (migrations incluidas)
git status
git add -A
git commit -m "Estado actual del sistema de inventario"

# 2. Subir a GitHub (crear el repo primero en github.com)
git remote add origin https://github.com/TU_USUARIO/mayu-bodega.git
git push -u origin main
```

---

## 2. Ajustes de código para producción

### 2.1 `render.yaml` (nuevo, en la raíz)

Render necesita saber cómo construir y arrancar. Crea `render.yaml`:

```yaml
services:
  - type: web
    name: mayu-bodega
    runtime: python
    plan: free
    buildCommand: |
      cd backend && pip install -r requirements.txt && \
      python manage.py migrate && \
      python manage.py collectstatic --noinput && \
      python manage.py seed_roles && \
      python manage.py seed_demo && \
      python manage.py seed_stock && \
      cd ../frontend && npm install && npm run build
    startCommand: cd backend && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.14
      - key: NODE_VERSION
        value: 22.x
      - key: DJANGO_DEBUG
        value: "false"
      - key: DJANGO_ALLOWED_HOSTS
        value: "*"
      - key: DJANGO_SECRET_KEY
        generateValue: true
      - key: DJANGO_CSRF_TRUSTED_ORIGINS
        value: "https://mayu-bodega.onrender.com"
      - key: MAYU_DEMO_PASSWORD
        sync: false
      - key: PORT
        value: 10000
```

Notas:
- Los `seed_*` son idempotentes, se pueden repetir en cada build sin duplicar.
- `gunicorn` **no está** en `backend/requirements.txt` todavía. Hay que agregarlo:

```powershell
Add-Content backend\requirements.txt "gunicorn==23.0.0"
```

- `PORT` lo inyecta Render; `runserver` no vale para producción, se usa gunicorn.

### 2.2 Servir la SPA (React Router) desde Django

El frontend usa `BrowserRouter` y la API es same-origin (rutas relativas, ver
`frontend/src/lib/apiClient.ts` y `mediaUrl.ts`). En producción Django debe servir:

- `/` → `frontend/dist/index.html` (la app)
- `/assets/*` → el build de Vite
- `/media/*` → las fotos de productos (**hoy solo se sirven con `DEBUG=True`**)

Añade en `backend/config/urls.py`:

```python
from django.conf import settings
from django.conf.urls.static import static
from django.http import FileResponse, HttpResponse, JsonResponse
from django.urls import include, path, re_path
from django.views.decorators.cache import never_cache
from django.views.static import serve

DIST_DIR = settings.BASE_DIR.parent / 'frontend' / 'dist'


@never_cache
def spa(request):
    index = DIST_DIR / 'index.html'
    if index.exists():
        return FileResponse(open(index, 'rb'), content_type='text/html')
    return JsonResponse({'error': 'Frontend sin compilar'}, status=503)


def assets(request, ruta):
    archivo = (DIST_DIR / 'assets' / ruta).resolve()
    if not str(archivo).startswith(str((DIST_DIR / 'assets').resolve())) or not archivo.is_file():
        return HttpResponse(status=404)
    return FileResponse(open(archivo, 'rb'))


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/core/', include('core.urls')),
    path('api/', include('catalog.urls')),
    path('api/', include('rates.urls')),
    path('api/', include('inventory.urls')),
    path('api/', include('customers.urls')),
    path('api/', include('sales.urls')),
    path('assets/<path:ruta>', assets, name='assets'),
    # El grupo debe llamarse `path`: es el keyword que espera `serve`.
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    re_path(r'^(?!api/|admin/|assets/|media/|static/).*$', spa, name='spa'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

> **Dos trampas verificadas en esta app, no adivinadas:**
>
> 1. **`path('', spa)` NO es un catch-all.** Solo matchea el resto vacío, así que
>    la raíz carga pero `/ventas`, `/productos` o `/creditos` devuelven 404 y
>    React Router no arranca al recargar. Hace falta una expresión regular como
>    la de arriba. El negativo `(?!api/|admin/|...)` mantiene los 404 de la API
>    como JSON en vez de devolverles el `index.html`.
> 2. **WhiteNoise no puede servir `media/`.** `WHITENOISE_ROOT` se monta en `/`
>    sin prefijo (en `whitenoise/middleware.py`, `add_files(root)` va sin
>    argumento `prefix`), de modo que las fotos responderían en
>    `/products/1/xxx.webp` en lugar de `/media/products/1/xxx.webp` y se
>    rompería cada URL ya guardada. Por eso `media` va con una ruta explícita
>    sobre `django.views.static.serve`, que sí funciona con `DEBUG=False`.
>    WhiteNoise queda a cargo de `STATIC_ROOT` (el bundle de Vite), que es lo
>    que resuelve bien.
>
> Sobre la vista `assets`: compara la ruta resuelta contra la raíz del build, así
> que un `../..` no lee archivos de fuera. Conviene comprobarlo antes de
> desplegar (`backend/tools/` no lo cubre todavía).
>
> Para algo real, mueve `media` a un bucket S3/R2 o al disco persistente de la
> sección 5.

### 2.3 Variables de entorno

Render inyecta variables directamente (python-dotenv no las necesita ahí, el
`.env` local está en `.gitignore` y no viaja). Valores mínimos en Render:

| Variable | Valor |
| --- | --- |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_ALLOWED_HOSTS` | `*` |
| `DJANGO_SECRET_KEY` | Valor fuerte (no el de `.env`) |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://TU-NOMBRE.onrender.com` |
| `MAYU_DEMO_PASSWORD` | Contraseña propia (nunca `mayu1234` en producción) |

### 2.4 Cómo viaja la data a la demo

El disco de Render es efímero, así que el build arranca de cero. Para esta demo
se versionan a propósito `backend/db.sqlite3` y `backend/media/` (las dos líneas
están comentadas en `.gitignore`). El build solo hace `migrate` + `collectstatic`
sobre esa copia: **no se corren los `seed_*`**, porque la copia ya los tiene
aplicados y `seed_demo` volvería a insertar artículos de prueba.

Dos advertencias que solo aparecen al versionar la base:

- **Los tokens de DRF no dependen del `SECRET_KEY`.** Render genera una clave
  nueva en cada despliegue, pero los tokens que viajan dentro de `db.sqlite3`
  seguirían dando acceso a la API pública. Límpialos antes de commitear:
  `..\.venv\Scripts\python.exe backend\tools\purge_api_tokens.py --apply`
- **Los hashes de contraseña también viajan.** Hoy son usuarios de prueba
  (`admin`, `gerente`, `almacenero`, `cajero`, todos con la misma contraseña de
  demostración). Antes de usar esto con una bodega real, deja de versionarse la
  base y pasa a la sección 5.

> Por qué no hay `MAYU_DEMO_PASSWORD` en `render.yaml`: los usuarios ya vienen
> creados dentro de la base versionada, así que la contraseña se cambia en el
> panel de admin, no por variable de entorno.

---

## 3. Build local (anti-sorpresas)

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput

cd ..\frontend
npm install
npm.cmd run build   # tsc + vite build; falla sí hay errores de tipos
```

> En PowerShell, `npm` puede estar bloqueado por la política de ejecución — usa
> `npm.cmd`.

---

## 4. Push → auto-deploy → verificar

Render re-despliega en cada `git push` a `main` (~2-3 min, igual que el otro
proyecto).

```powershell
cd "C:\Users\HellRaiser\Documents\Mayu Bodega"
git add -A
git commit -m "..." 
git push origin main
```

Verificación:

```powershell
# 1. La SPA responde (debe devolver el index.html de React)
Invoke-WebRequest -Uri "https://TU-NOMBRE.onrender.com/" -UseBasicParsing

# 2. El login responde (pantalla de entrada)
Invoke-WebRequest -Uri "https://TU-NOMBRE.onrender.com/api/core/auth/login/" -Method Post `
  -ContentType "application/json" -Body '{"username":"admin","password":"TU_PASSWORD"}' -UseBasicParsing

# 3. Un asset del build nuevo existe
Invoke-WebRequest -Uri "https://TU-NOMBRE.onrender.com/assets/" -UseBasicParsing   # 404 esperado si no hay ruta vacía, prueba un hash concreto
```

---

## 5. Los datos en "free" (el punto crítico)

En plan free, cada redeploy entrega un sistema de archivos **vacío**:
`db.sqlite3` y `backend/media/` desaparecen. Para dejarlo como estaba después de
un deploy, hay que **descargar antes y re-subir después** (mismo ritual que los
bots, pero con dos artefactos).

Crear `scripts/respaldar_mayu.ps1`:

```powershell
param([string]$Backend = "C:\Users\HellRaiser\Documents\Mayu Bodega\backend")

$ts = Get-Date -Format "yyyy-MM-dd_HHmmss"
$dir = "backups_mayu"
New-Item -ItemType Directory -Force -Path $dir | Out-Null

# Sistema no corre: copiar archivos directamente (si no, usar dump vía Django shell)
Copy-Item "$Backend\db.sqlite3" "$dir\db_$ts.sqlite3"
if (Test-Path "$Backend\media") {
  Copy-Item "$Backend\media" "$dir\media_$ts" -Recurse
}
Write-Output "Respaldo en $dir (db + media)"
```

Y `scripts/restaurar_mayu.ps1` para re-subirlos al servidor tras el redeploy
(subida vía panel de Render o volumen, o por un endpoint admin protegido; no hay
API pública para subir la BD completa — **esto es una limitación real del plan free**).

---

## Alternativa persistente (recomendada)

Para no perder negocio, la vía correcta es cambiar **Solo el almacenamiento**, no
el flujo de deploy:

1. **PostgreSQL gestionado en Render** (hay capa gratuita) y en `settings.py` leer
   `DATABASE_URL` si existe, sino SQLite local. Las imágenes siguen necesitando
   disco o bucket.
2. **Disco persistente (Render Disk)**: el plan **no lo incluye en free**; es
   pagado. Monta el disco en `/data`, apunta `MEDIA_ROOT` y `db.sqlite3` ahí, y
   así sobreviven los redeploys sin scripts.
3. En cualquier caso, mantén `seed_roles`/`seed_demo`/`seed_stock` en el build
   (idempotentes) y `sync_bcv_rate` programado cada hora (en el servidor: cron o
   un endpoint admin protegido + Programador de Windows si el servidor es local).

---

## Checklist final

- [x] Repo con remoto en GitHub, rama `main`, todo commiteado.
- [x] `render.yaml` creado y `gunicorn` + `whitenoise` en `backend/requirements.txt`.
- [x] `urls.py` sirve SPA + assets + media en producción, con `DEBUG=False`
      verificado en local: `/`, `/ventas`, `/productos`, `/vender`, `/creditos` y
      `/ajustes` devuelven 200; la API conserva el JSON en sus 401; 10 fotos
      reales de la API devuelven 200 `image/webp`; el traversal a `db.sqlite3` o
      `.env` no filtra nada.
- [x] Build local pasa (`npm.cmd run build`, `collectstatic`, `manage.py check`,
      156 tests, `npm.cmd run lint`).
- [x] `db.sqlite3` y `backend/media/` versionados para que la demo arranque con
      contenido, y tokens de API purgados antes del push.
- [ ] Blueprint aplicado en Render y variables de entorno confirmadas.
- [ ] Verificado login + página principal después del deploy.
- [ ] Cambiar la contraseña de `mayu1234` antes de enseñar la URL.
- [ ] Decidido el camino de persistencia real (Postgres o Disco).