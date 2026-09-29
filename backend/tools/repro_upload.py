"""Upload a photo to a product through the real HTTP endpoint.

Writes data, so it needs ``--apply``. Useful to reproduce a bug report exactly
as the mobile client would, instead of guessing from the ORM.

    python tools/repro_upload.py --product P000011 --file foto.jpg
    python tools/repro_upload.py --product P000011 --file foto.jpg --apply
"""

import argparse
import json
import mimetypes
from pathlib import Path

from _common import (
    DEFAULT_API_URL,
    api_session,
    fail,
    heading,
    ok,
    request,
    require_apply,
    setup_django,
)

setup_django()

from catalog.models import Product  # noqa: E402


def resolve_product(base_url: str, token: str, code: str):
    status, body = request('GET', f'{base_url}/api/products/?search={code}', token)
    if status != 200:
        raise SystemExit(f'no se pudo buscar el producto ({status})')
    results = json.loads(body).get('results', [])
    for product in results:
        if product.get('code') == code:
            return product
    raise SystemExit(f'no se encontró el producto {code}')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--product', required=True, help='código de producto')
    parser.add_argument('--file', required=True, type=Path, help='archivo a subir')
    parser.add_argument('--api-url', default=DEFAULT_API_URL)
    parser.add_argument('--username', default=None)
    parser.add_argument('--primary', action='store_true', help='marcarlo como principal')
    parser.add_argument('--apply', action='store_true', help='ejecutar la subida')
    args = parser.parse_args()

    if not args.file.is_file():
        raise SystemExit(f'no existe el archivo {args.file}')
    if args.file.stat().st_size == 0:
        raise SystemExit('el archivo está vacío')

    content_type = mimetypes.guess_type(args.file.name)[0] or 'image/jpeg'
    base_url, token = api_session(args.api_url, args.username)
    product = resolve_product(base_url, token, args.product)

    heading(f'Subir {args.file.name} a {product["code"]} - {product["name"]}')
    print(f'  tipo     : {content_type}')
    print(f'  peso     : {args.file.stat().st_size} bytes')
    print(f'  principal: {args.primary}')

    require_apply(args.apply, f'se crearía una foto para {product["code"]}')

    from _common import multipart

    fields = {'product': product['id']}
    if args.primary:
        fields['is_primary'] = 'true'
    body, content_header = multipart(
        fields, 'image', args.file.name, args.file.read_bytes(), content_type
    )

    status, response_body = request(
        'POST',
        f'{base_url}/api/product-images/',
        token,
        data=body,
        headers={'Content-Type': content_header},
        timeout=60,
    )
    print(f'  HTTP {status}')
    if status not in (200, 201):
        fail(response_body)
        return 1

    created = json.loads(response_body)
    ok(f"creada la foto #{created['id']} ({created['width']}x{created['height']})")
    print(f"  url      : {created['url']}")
    print(f"  miniatura: {created['thumbnail_url']}")
    print(f"  principal: {created['is_primary']}")

    verify_status, _ = request('GET', created['url'], token, headers={'Accept': 'image/*'})
    if verify_status == 200:
        ok('la URL de la foto responde HTTP 200')
    else:
        fail(f'la URL de la foto respondió HTTP {verify_status}')

    print(f'\nPara revertir: python tools/repro_delete.py --image-id {created["id"]} --apply')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
