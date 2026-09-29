"""Verify that every photo referenced by the API is actually served.

Read only, but it needs a running server. Useful after a media folder is moved,
restored from a backup or cleaned up by mistake.

    python tools/check_urls.py
    python tools/check_urls.py --api-url http://127.0.0.1:8000
"""

import argparse
import json

from _common import DEFAULT_API_URL, api_session, fail, heading, ok, request, setup_django, warn

setup_django()

from catalog.models import ProductImage  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--api-url', default=DEFAULT_API_URL)
    parser.add_argument('--username', default=None)
    args = parser.parse_args()

    images = list(ProductImage.objects.select_related('product').order_by('pk'))
    heading(f'Comprobando {len(images)} fotos contra {args.api_url}')
    if not images:
        print('  (no hay fotos en la base de datos)')
        return 0

    base_url, token = api_session(args.api_url, args.username)

    # The API only serialises absolute URLs when a request is in context, so the
    # list endpoint is the source of truth for what the browser will fetch.
    status, body = request('GET', f'{base_url}/api/products/?page_size=200', token)
    if status != 200:
        fail(f'no se pudo listar productos ({status})')
        return 1

    payload = json.loads(body)
    checked, broken = 0, []
    for product in payload.get('results', []):
        for image in product.get('images', []):
            url = image.get('thumbnail_url') or image.get('url')
            if not url:
                continue
            checked += 1
            code, _ = request('GET', url, token, headers={'Accept': 'image/*'})
            if code != 200:
                broken.append((product['code'], url, code))

    for code, url, status_code in broken:
        fail(f'{code} -> HTTP {status_code} {url}')
    if broken:
        return 1

    ok(f'{checked} URLs responden HTTP 200')
    orphans = [
        image
        for image in images
        if not image.image or not image.image.storage.exists(image.image.name)
    ]
    for image in orphans:
        warn(f'fila #{image.pk} apunta a un archivo inexistente')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
