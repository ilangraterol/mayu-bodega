"""Full HTTP smoke test of the product photo lifecycle.

Read only by default: it logs in, lists the catalogue and verifies that every
advertised photo is served. With ``--apply`` it also creates a throwaway
product, uploads a generated photo, promotes it, deletes it and removes the
product, so the whole path is exercised end to end.

    python tools/test_image_api.py
    python tools/test_image_api.py --apply
"""

import argparse
import json
from io import BytesIO

from _common import (
    DEFAULT_API_URL,
    api_session,
    fail,
    heading,
    multipart,
    ok,
    request,
    setup_django,
    warn,
)

setup_django()

from PIL import Image  # noqa: E402


def sample_photo(width: int = 900, height: int = 600) -> bytes:
    """A deterministic in-memory JPEG so the tool needs no fixture file."""
    buffer = BytesIO()
    Image.new('RGB', (width, height), (32, 96, 160)).save(buffer, format='JPEG', quality=88)
    return buffer.getvalue()


def check_serving(base_url: str, token: str) -> int:
    heading('1. Catálogo y fotos servidas')
    status, body = request('GET', f'{base_url}/api/products/?page_size=200', token)
    if status != 200:
        fail(f'listado de productos respondió {status}')
        return 1
    products = json.loads(body).get('results', [])
    total_images = sum(len(p.get('images', [])) for p in products)
    ok(f'{len(products)} productos, {total_images} fotos')

    problems = 0
    for product in products:
        for image in product.get('images', []):
            for key in ('url', 'thumbnail_url'):
                url = image.get(key)
                if not url:
                    continue
                code, _ = request('GET', url, token, headers={'Accept': 'image/*'})
                if code != 200:
                    fail(f'{product["code"]} {key} -> HTTP {code}')
                    problems += 1
    if not problems:
        ok('todas las URLs de imagen responden HTTP 200')
    return problems


def check_lifecycle(base_url: str, token: str) -> int:
    heading('2. Ciclo de vida completo sobre un producto temporal')
    problems = 0

    status, body = request(
        'POST',
        f'{base_url}/api/products/',
        token,
        data=json.dumps(
            {
                'name': 'Producto temporal de verificación',
                'brand': 'TOOLS',
                'unit_of_measure': 'UNIDAD',
                'cost_usd': '1.00',
                'price_usd': '1.00',
            }
        ).encode(),
        headers={'Content-Type': 'application/json'},
    )
    if status not in (200, 201):
        fail(f'no se pudo crear el producto temporal ({status}): {body[:200]}')
        return 1
    product = json.loads(body)
    ok(f'producto temporal #{product["id"]} {product["code"]}')

    created_ids: list[int] = []
    try:
        for index, is_primary in enumerate((True, False)):
            payload, header = multipart(
                {
                    'product': product['id'],
                    **({'is_primary': 'true'} if is_primary else {}),
                },
                'image',
                f'verificacion{index}.jpg',
                sample_photo(800 + index * 100, 600),
                'image/jpeg',
            )
            status, body = request(
                'POST',
                f'{base_url}/api/product-images/',
                token,
                data=payload,
                headers={'Content-Type': header},
                timeout=60,
            )
            if status not in (200, 201):
                fail(f'subida {index} respondió {status}: {body[:200]}')
                problems += 1
                continue
            image = json.loads(body)
            created_ids.append(image['id'])
            flag = 'principal' if image['is_primary'] else 'secundaria'
            ok(f'subida {index}: #{image["id"]} {image["width"]}x{image["height"]} {flag}')
            if image['is_primary'] != is_primary:
                fail(f'subida {index}: is_primary inesperado')
                problems += 1
            if not image['url'].endswith('.webp'):
                warn(f'subida {index}: la URL no es WebP ({image["url"]})')

        if len(created_ids) == 2:
            status, body = request(
                'POST', f'{base_url}/api/product-images/{created_ids[1]}/set_primary/', token
            )
            if status != 200:
                fail(f'set_primary respondió {status}: {body[:200]}')
                problems += 1
            elif json.loads(body)['is_primary']:
                ok(f'set_primary promovió la foto #{created_ids[1]}')
            else:
                fail('set_primary no promovió la foto')
                problems += 1

        for image_id in created_ids:
            status, body = request('DELETE', f'{base_url}/api/product-images/{image_id}/', token)
            if status not in (200, 204):
                fail(f'borrado #{image_id} respondió {status}: {body[:160]}')
                problems += 1
            else:
                ok(f'borrado #{image_id} -> HTTP {status}')
    finally:
        status, _ = request('DELETE', f'{base_url}/api/products/{product["id"]}/', token)
        if status in (200, 204):
            ok(f'producto temporal #{product["id"]} eliminado')
        else:
            warn(f'no se pudo eliminar el producto temporal ({status}); bórralo a mano')

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-url', default=DEFAULT_API_URL)
    parser.add_argument('--username', default=None)
    parser.add_argument(
        '--apply', action='store_true', help='además de leer, crear y borrar datos'
    )
    args = parser.parse_args()

    base_url, token = api_session(args.api_url, args.username)
    heading(f'Conectado a {base_url}')

    problems = check_serving(base_url, token)
    if args.apply:
        problems += check_lifecycle(base_url, token)
    else:
        heading('2. Ciclo de vida completo')
        print('  omitido (solo lectura). Use --apply para ejecutarlo.')

    heading('Resultado')
    if problems:
        fail(f'{problems} problema(s) detectado(s)')
        return 1
    ok('todo en orden')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
