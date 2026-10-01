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
from django.urls import include, path
from django.views.decorators.cache import never_cache

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
    path('', spa, name='spa'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

> **Cuidado:** la ruta `''` (catch-all) debe ir al final y sirve `index.html` para
> cualquier ruta no API, para que React Router funcione. En producción `media`
> se sirve por `whitenoise` o por un servicio de almacenamiento; si no, las fotos
> no cargarán. La solución mínima es [whitenoise con `STORAGES`](https://whitenoise.readthedocs.io/);
> para algo real, usa un bucket S3/R2 o el disco persistente de la sección 5.

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

- [ ] Repo con remoto en GitHub, rama `main`, todo commiteado.
- [ ] `render.yaml` creado y `gunicorn` en `backend/requirements.txt`.
- [ ] `urls.py` sirve SPA + assets + media en producción.
- [ ] Build local pasa (`npm.cmd run build`, `collectstatic`).
- [ ] Variables de entorno puestas en Render (`SECRET_KEY`, `MAYU_DEMO_PASSWORD`, etc.).
- [ ] **Respaldo de `db.sqlite3` + `media` ANTES de cada push** que dispare redeploy.
- [ ] Verificado login + página principal después del deploy.
- [ ] Decidido el camino de persistencia real (Postgres o Disco).