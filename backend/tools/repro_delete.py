"""Delete a product photo through the real HTTP endpoint and verify the file.

Writes data, so it needs ``--apply``. This is the tool that proves the Windows
locking bug stays fixed: after a 204 the row is gone *and* the file is no
longer on disk.

    python tools/repro_delete.py --image-id 46
    python tools/repro_delete.py --image-id 46 --apply
"""

import argparse
import json

from _common import (
    DEFAULT_API_URL,
    api_session,
    fail,
    heading,
    ok,
    request,
    require_apply,
    setup_django,
    warn,
)

setup_django()

from catalog.models import ProductImage  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image-id', required=True, type=int)
    parser.add_argument('--api-url', default=DEFAULT_API_URL)
    parser.add_argument('--username', default=None)
    parser.add_argument('--apply', action='store_true', help='ejecutar el borrado')
    args = parser.parse_args()

    row = ProductImage.objects.select_related('product').filter(pk=args.image_id).first()
    if row is None:
        raise SystemExit(f'no existe la foto #{args.image_id}')

    names = [field.name for field in (row.image, row.thumbnail) if field]
    storage = row.image.storage if row.image else None

    heading(f'Borrar foto #{row.pk} de {row.product.code} - {row.product.name}')
    print(f'  principal : {row.is_primary}')
    for name in names:
        print(f'  archivo   : {name}')
        if storage is not None and storage.exists(name):
            print(f'              {storage.size(name)} bytes en disco')
    if not names:
        warn('la fila no tiene archivos asociados, solo se eliminará el registro')

    require_apply(args.apply, f'se borraría la foto #{row.pk} de {row.product.code}')

    base_url, token = api_session(args.api_url, args.username)
    status, body = request('DELETE', f'{base_url}/api/product-images/{row.pk}/', token)
    print(f'  HTTP {status} {body[:120]}')
    if status not in (200, 204):
        fail('el borrado falló')
        return 1

    problems = 0
    if ProductImage.objects.filter(pk=row.pk).exists():
        fail('la fila sigue en la base de datos')
        problems += 1
    else:
        ok('la fila se eliminó')

    for name in names:
        if storage is not None and storage.exists(name):
            fail(f'el archivo quedó en disco: {name}')
            problems += 1
        else:
            ok(f'el archivo se eliminó: {name}')

    # The API must no longer advertise a photo that was just removed.
    status, body = request('GET', f'{base_url}/api/products/{row.product_id}/', token)
    if status == 200:
        remaining = [i['id'] for i in json.loads(body).get('images', [])]
        if row.pk in remaining:
            fail('el producto sigue listando la foto borrada')
            problems += 1
        else:
            ok('el producto ya no lista la foto borrada')
    else:
        warn(f'no se pudo releer el producto ({status})')

    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
