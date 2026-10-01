# Herramientas de diagnóstico y mantenimiento

Scripts reutilizables del backend. Existen para **no reescribir** el mismo
script de prueba cada vez que hay que investigar algo: revisa esta carpeta
primero, ejecuta el que corresponda y, si falta una variación, añade un
argumento al script más cercano en vez de crear un archivo temporal.

## Reglas de esta carpeta

1. **Solo lectura por defecto.** Cualquier cosa que escriba en la base de datos
   o borre un archivo exige `--apply` y primero imprime el plan.
2. **Sin credenciales en el código.** La contraseña sale de `MAYU_PASSWORD` o de
   un prompt interactivo. Nunca se escribe en disco ni se imprime en logs.
3. **Nada de scripts sueltos en la raíz del backend.** Si un script de
   investigación deja de ser útil, se elimina de aquí y no fuera.
4. **Reutilizar antes de crear.** Antes de escribir un script nuevo, lee el
   `README.md` y los `--help` de los existentes.

## Uso

Desde `backend/`, con el entorno virtual del proyecto:

```powershell
..\.venv\Scripts\python.exe tools\check_images.py
```

Variables opcionales:

| Variable         | Por defecto                  | Para qué                          |
| ---------------- | ---------------------------- | --------------------------------- |
| `MAYU_API_URL`   | `http://127.0.0.1:8000`      | Servidor contra el que se prueba  |
| `MAYU_USERNAME`  | `admin`                      | Usuario de la API                 |
| `MAYU_PASSWORD`  | (pregunta interactiva)       | Contraseña de la API              |

## Catálogo

| Script                       | Qué hace                                                        | Escribe |
| ---------------------------- | --------------------------------------------------------------- | ------- |
| `check_images.py`            | Auditoría del catálogo: quién tiene foto, filas rotas, principales | no      |
| `check_urls.py`              | Comprueba que cada foto referenciada responde HTTP 200           | no      |
| `check_seed_conflicts.py`    | Conflictos que harían fallar `manage.py seed_demo` (códigos de barra, categorías) | no |
| `restore_seed_names.py`      | Devuelve a los artículos el nombre descriptivo que `seed_demo` acortó | con `--apply` |
| `inspect_image.py`           | Formato, tamaño, dimensiones y prueba de bloqueo de un archivo   | no      |
| `test_image_api.py`          | Humo del ciclo completo por HTTP (listar, con `--apply`, crear/borrar) | con `--apply` |
| `repro_upload.py`            | Sube una foto por la API como lo haría el móvil                  | con `--apply` |
| `repro_delete.py`            | Borra una foto por la API y verifica que el archivo desaparece    | con `--apply` |
| `cleanup_image_rows.py`      | Repara filas huérfanas, principales duplicadas y archivos sueltos | con `--apply` |
| `check_category_filter.py`   | Comprueba que `GET /api/products/?category=<id>` filtra de verdad y cuenta los artículos sin categoría | no      |
| `purge_api_tokens.py`        | Borra los tokens de DRF antes de subir `db.sqlite3` al repo, para que no den acceso a la API pública | con `--apply` |

`_common.py` no es un script: contiene el arranque de Django, el cliente HTTP y
los ayudantes de salida que comparten todos los demás.

## Ejemplos

```powershell
# Ver quién no tiene foto
..\.venv\Scripts\python.exe tools\check_images.py --missing-only

# Revisar que nada esté bloqueado en Windows
..\.venv\Scripts\python.exe tools\inspect_image.py --product P000011

# Ver por qué fallaría la carga de datos de demostración
..\.venv\Scripts\python.exe tools\check_seed_conflicts.py

# Reproducir el ciclo completo de subida/baja contra el servidor local
..\.venv\Scripts\python.exe tools\test_image_api.py --apply

# Antes de commitear db.sqlite3, deja la base sin tokens de API válidos
..\.venv\Scripts\python.exe tools\purge_api_tokens.py --apply
```

## Añadir una herramienta nueva

1. Créala en `backend/tools/` y reutiliza `_common.setup_django()` y
   `_common.api_session()`; no repitas la lógica de login ni de Django.
2. Todo lo que escriba debe pasar por `_common.require_apply()`.
3. Añade una línea a la tabla de este README.
4. Ejecuta el script al menos una vez en modo lectura y confirma que la salida
   es útil.
