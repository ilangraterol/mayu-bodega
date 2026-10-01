# Mayu Bodega

Sistema de inventario, ventas y crédito (fiado) para una bodega, con operación
nativa en **USD** y **VES** (Bolívares).

- **Backend:** Django 6 + Django REST Framework (SQLite, auth por token).
- **Frontend:** React + TypeScript + Vite + React Router + Tailwind (mobile-first).
- **Tasa de cambio:** se sincroniza con el BCV; cada venta y cada abono congelan
  la tasa que estaba vigente en ese instante.

## Requisitos

- Python 3.14+
- Node.js 20+

## Arranque del backend

```powershell
# 1. Entorno virtual (desde la raíz del proyecto)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Dependencias
pip install -r backend\requirements.txt

# 3. Configuración
copy .env.example .env

# 4. Base de datos y datos iniciales
cd backend
python manage.py migrate
python manage.py seed_roles      # grupos y permisos
python manage.py seed_demo       # usuarios, catálogo, tasa, clientes y ventas de ejemplo
python manage.py seed_stock      # existencias iniciales (opcional)

# 5. Servidor
python manage.py runserver 8000
```

En PowerShell, `npm.ps1` suele estar bloqueado por la política de ejecución.
Si ocurre, usa `npm.cmd` en lugar de `npm`.

### Comandos disponibles

| Comando | Qué hace |
| --- | --- |
| `seed_roles` | Crea los grupos y permisos de los roles |
| `seed_demo` | Datos de ejemplo: usuarios, catálogo, tasa, clientes y ventas |
| `seed_stock` | Existencias iniciales, siempre como movimiento de inventario |
| `sync_bcv_rate` | Consulta la tasa oficial al BCV |
| `import_costazul` | Importa el catálogo de Cost Azul desde un CSV |

`seed_demo` y `seed_stock` son idempotentes: se pueden volver a ejecutar.

### Usuarios de demostración

Contraseña para todos: `mayu1234`. Se puede cambiar con la variable de entorno
`MAYU_DEMO_PASSWORD`; fuera de desarrollo define siempre una propia para no dejar
cuentas de ejemplo con una contraseña conocida.

| Usuario | Rol | Puede |
| --- | --- | --- |
| `admin` | Administrador | Todo |
| `gerente` | Gerente | Catálogo, tasa, inventario, clientes, ventas, configuración |
| `almacenero` | Almacenero | Catálogo, imágenes, entradas, notas de salida |
| `cajero` | Cajero | Ventas, clientes, deudas y abonos |

### Tasa del BCV

```powershell
python manage.py sync_bcv_rate
```

Programar cada hora con el Programador de tareas de Windows:

```
powershell.exe -NoProfile -Command "& '<ruta>\.venv\Scripts\python.exe' '<ruta>\backend\manage.py' sync_bcv_rate"
```

Si la consulta falla, un administrador puede registrar una tasa **manual** desde
`POST /api/rates/manual/` sin sobrescribir el historial oficial del BCV.

## Arranque del frontend

El frontend necesita el backend corriendo en `http://127.0.0.1:8000`; Vite hace
de proxy de `/api` y `/media`, así que no hay CORS ni URLs absolutas.

```powershell
cd frontend
npm install          # solo la primera vez
npm run dev          # http://127.0.0.1:5173
```

En PowerShell, `npm.ps1` suele estar bloqueado por la política de ejecución.
Si ocurre, usa `npm.cmd` en lugar de `npm`.

### Scripts del frontend

| Comando | Qué hace |
| --- | --- |
| `npm run dev` | Servidor de desarrollo con HMR |
| `npm run build` | `tsc -b` + build de producción en `dist/` |
| `npm run lint` | `oxlint` sobre `src/` |
| `npm run preview` | Sirve el build de producción |

Los tipos de la API viven en `frontend/src/types/api.ts` y todas las rutas en
`frontend/src/lib/endpoints.ts`; ese archivo es la fuente de verdad y está
verificado contra los routers de Django.

### Recargo en el punto de venta

`SurchargePicker` acompaña cada línea del carrito. Se muestra contraído con el
porcentaje ya resuelto y de dónde salió, así que el caso normal es no tocarlo.
Al abrirlo aparecen los atajos (`0`, `3`, `5`, `10`, `15`, `30`) y un campo libre
de `0` a `100%`. Elegir el valor heredado lo devuelve al catálogo, que es como se
evita fijar un artículo por una simple confirmación. Todo importe que se cobra lo
calcula el servidor en `POST /api/sales/quote/`; el resumen solo muestra el
desglose por línea que devuelve.

## Tests

```powershell
cd backend
python manage.py test
```

## Herramientas de diagnóstico

Los scripts de verificación y reparación del backend viven en
`backend/tools/` y son **solo lectura por defecto**: los que escriben o borran
exigen `--apply` e imprimen el plan antes de actuar.

```powershell
cd backend

python tools\check_images.py --missing-only    # quién no tiene foto
python tools\inspect_image.py --product P000011 # formato, tamaño y bloqueos
python tools\check_urls.py                      # cada foto responde HTTP 200
python tools\test_image_api.py --apply          # ciclo completo de subida y baja
```

Consulta el índice completo en [`backend/tools/README.md`](backend/tools/README.md).

## Búsqueda sin acentos

Todas las listas de la API usan `UnaccentSearchFilter`, así que `azu`, `azucar`,
`AZUCAR` y `Azúcar` encuentran lo mismo en productos, clientes, ventas, deudas,
pagos, entradas, notas de salida y Kardex.

SQLite no trae `unaccent`, así que `core/search.py` registra una función
equivalente en cada conexión. Los términos de un solo carácter se comparan
literalmente para que `ñ` no se convierta en una búsqueda por `n`.

## API

Todas las rutas cuelgan de `/api/`. Salvo `login`, requieren
`Authorization: Token <clave>`.

| Método | Ruta | Descripción |
| --- | --- | --- |
| `POST` | `/api/core/auth/login/` | Devuelve token y roles |
| `POST` | `/api/core/auth/logout/` | Invalida el token |
| `GET` | `/api/core/auth/me/` | Usuario autenticado |
| `GET`/`PATCH` | `/api/core/config/store/` | Configuración (recargo, venta con stock 0) |
| `GET/POST` | `/api/products/` | Catálogo |
| `POST` | `/api/products/barcode_lookup/?code=` | Buscar por código de barra |
| `GET/POST` | `/api/categories/` | Categorías y su recargo compartido |
| `GET` | `/api/categories/surcharge-presets/` | Atajos de recargo sugeridos |
| `GET/POST` | `/api/product-images/` | Imágenes (multipart) |
| `POST` | `/api/product-images/{id}/set_primary/` | Marcar imagen principal |
| `GET` | `/api/rates/` | Historial de tasas |
| `GET` | `/api/rates/current/` | Tasa vigente |
| `POST` | `/api/rates/manual/` | Tasa manual de respaldo |
| `GET` | `/api/stock-movements/` | Kardex inmutable |
| `POST` | `/api/goods-entries/` | Entrada de mercancía |
| `POST` | `/api/goods-entries/{id}/cancel/` | Anular entrada |
| `GET/POST` | `/api/exit-notes/` | Nota de salida |
| `GET` | `/api/exit-notes/reasons/` | Motivos de salida disponibles |
| `POST` | `/api/exit-notes/{id}/cancel/` | Anular nota |
| `GET/POST` | `/api/customers/` | Clientes |
| `GET` | `/api/customers/{id}/statement/` | Estado de cuenta del cliente |
| `GET/POST` | `/api/sales/` | Ventas pagadas y fiadas |
| `POST` | `/api/sales/quote/` | Cotizar sin registrar |
| `POST` | `/api/sales/{id}/void/` | Anular venta |
| `GET` | `/api/debts/` | Deudas de clientes |
| `GET/POST` | `/api/debts/{id}/payments/` | Registrar abono |
| `POST` | `/api/debt-payments/{id}/void/` | Anular abono |
| `GET` | `/api/sales-summary/` | Resumen del día |

## Reglas del dominio

- **Dinero:** todo importe es `Decimal`. Está prohibido `float`/`double`.
- **Recargo por línea:** el porcentaje se resuelve en este orden:
  `artículo > categoría > tienda`. En el carrito, el cajero puede ajustarlo por
  línea. Solo se envía al servidor cuando se elige un valor **distinto** al que ya
  resolvió el catálogo, así que confirmar el valor heredado nunca fija un
  artículo. Al crear la venta, un valor distinto sí queda como nuevo recargo
  propio del artículo. `quote` no escribe nada.
- **Stock:** cada cambio pasa por `inventory.services.record_movement`, que
  bloquea la fila del producto y corre dentro de una transacción.
- **Historial:** los movimientos no se borran. Las correcciones son movimientos
  opuestos (`origin=ANULACION`) o estados de anulación.
- **Tasa:** cada venta guarda la tasa aplicada. Un abono en VES re-precifica el
  saldo pendiente en USD con la tasa vigente al momento del pago.
- **Imágenes:** se re-codifican a WebP (máx. 1200px) y se genera un thumbnail
  (máx. 320px). La primera imagen del producto queda como principal.
- **Zona horaria:** `America/Caracas`. La base guarda UTC.

## Estructura

```
backend/
  config/      settings, urls, wsgi
  core/        auth, roles, permisos, configuración, dinero, búsqueda
  catalog/     categorías, productos e imágenes
  rates/       historial BCV y tasa manual
  inventory/   movimientos, entradas, notas de salida
  customers/   clientes
  sales/       ventas, deudas, abonos
  tools/       scripts de diagnóstico y reparación (ver tools/README.md)
frontend/
  src/
    pages/       pantallas
    components/  componentes reutilizables
    hooks/       acceso a datos con React Query
    lib/         cliente de API, endpoints y formato
    types/       tipos de la API
```
