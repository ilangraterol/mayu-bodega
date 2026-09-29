"""Catalogue photo audit: which products have images and which do not.

Read only. Reports the state of ``ProductImage`` against the product
catalogue, including rows whose file is missing on disk and products whose
primary flag is inconsistent.

    python tools/check_images.py
    python tools/check_images.py --missing-only
    python tools/check_images.py --limit 20
"""

import argparse

from _common import fail, heading, ok, setup_django, warn

setup_django()

from catalog.models import Product, ProductImage  # noqa: E402
from django.db.models import Count, Q  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--missing-only', action='store_true', help='solo productos sin foto'
    )
    parser.add_argument('--limit', type=int, default=0, help='máximo de filas a listar')
    args = parser.parse_args()

    products = Product.objects.annotate(image_count=Count('images'))
    total = products.count()
    with_images = products.filter(image_count__gt=0).count()

    heading('Resumen del catálogo')
    print(f'  productos totales      : {total}')
    print(f'  con al menos una foto  : {with_images}')
    print(f'  sin ninguna foto       : {total - with_images}')
    print(f'  filas ProductImage     : {ProductImage.objects.count()}')

    heading('Integridad de las filas')
    broken, no_primary, many_primary = [], [], []
    for image in ProductImage.objects.select_related('product').order_by('pk'):
        if not image.image or not image.image.storage.exists(image.image.name):
            broken.append(image)
    for product in products.filter(image_count__gt=0):
        primaries = product.images.filter(is_primary=True).count()
        if primaries == 0:
            no_primary.append(product)
        elif primaries > 1:
            many_primary.append(product)

    if broken:
        for image in broken:
            fail(f'fila #{image.pk} de {image.product.code}: falta el archivo en disco')
    else:
        ok('todas las filas apuntan a un archivo existente')

    if no_primary:
        for product in no_primary:
            warn(f'{product.code} tiene fotos pero ninguna marcada como principal')
    if many_primary:
        for product in many_primary:
            fail(f'{product.code} tiene varias fotos principales')
    if not no_primary and not many_primary and not broken:
        ok('una sola foto principal por producto, sin huérfanos')

    query = Q(image_count=0) if args.missing_only else Q(image_count__gt=0)
    rows = products.filter(query).order_by('code')
    if args.limit:
        rows = rows[: args.limit]

    heading('Productos sin foto' if args.missing_only else 'Productos con foto')
    empty = True
    for product in rows:
        empty = False
        if args.missing_only:
            print(f'  {product.code:<10} {product.name}')
    if empty:
        print('  (ninguno)')

    print()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
