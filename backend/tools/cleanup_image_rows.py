"""Find and repair inconsistencies in ``ProductImage``.

Read only by default: it prints a plan. ``--apply`` performs the repairs.

What it detects:

* filas cuyo archivo ya no existe en disco;
* productos con varias fotos marcadas como principales;
* productos con fotos pero ninguna principal;
* archivos huérfanos en ``media/`` que ninguna fila referencia.

    python tools/cleanup_image_rows.py
    python tools/cleanup_image_rows.py --apply
    python tools/cleanup_image_rows.py --missing-files-only
"""

import argparse

from _common import fail, heading, ok, require_apply, setup_django, warn

setup_django()

from catalog.models import Product, ProductImage  # noqa: E402
from django.conf import settings  # noqa: E402


def collect_missing_files():
    return [
        image
        for image in ProductImage.objects.select_related('product')
        if not image.image or not image.image.storage.exists(image.image.name)
    ]


def collect_duplicate_primaries():
    duplicated = []
    for product in Product.objects.filter(images__is_primary=True).distinct():
        count = product.images.filter(is_primary=True).count()
        if count > 1:
            duplicated.append((product, count))
    return duplicated


def collect_without_primary():
    result = []
    for product in Product.objects.filter(images__isnull=False).distinct():
        if not product.images.filter(is_primary=True).exists():
            result.append(product)
    return result


def collect_orphan_files():
    referenced = set()
    for image in ProductImage.objects.all():
        for field in (image.image, image.thumbnail):
            if field:
                referenced.add(field.name)

    storage = ProductImage._meta.get_field('image').storage
    orphans = []
    try:
        directories, files = storage.listdir('products')
    except (NotImplementedError, FileNotFoundError, OSError):
        return orphans

    for directory in directories:
        try:
            _, names = storage.listdir(f'products/{directory}')
        except (NotImplementedError, FileNotFoundError, OSError):
            continue
        for name in names:
            relative = f'products/{directory}/{name}'
            if relative not in referenced:
                orphans.append(relative)
    return orphans


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='ejecutar las reparaciones')
    parser.add_argument(
        '--missing-files-only', action='store_true', help='solo filas con archivo perdido'
    )
    args = parser.parse_args()

    missing = collect_missing_files()

    heading('Plan de limpieza')
    print(f'  filas con archivo perdido   : {len(missing)}')
    for image in missing:
        print(f'    #{image.pk} {image.product.code} -> {image.image.name if image.image else "(vacío)"}')

    if not args.missing_files_only:
        duplicates = collect_duplicate_primaries()
        print(f'  productos con 2+ principales: {len(duplicates)}')
        for product, count in duplicates:
            print(f'    {product.code} tiene {count} principales')

        without_primary = collect_without_primary()
        print(f'  productos sin principal     : {len(without_primary)}')
        for product in without_primary:
            print(f'    {product.code} {product.name}')

        orphans = collect_orphan_files()
        print(f'  archivos huérfanos          : {len(orphans)}')
        for name in orphans[:20]:
            print(f'    {name}')
        if len(orphans) > 20:
            print(f'    ... y {len(orphans) - 20} más')

    print(f'\n  media configurada en: {settings.MEDIA_ROOT}')

    if not args.apply:
        print('\nNada se modificó. Reemplace por --apply para aplicar este plan.')
        return 0

    require_apply(True, 'se aplicarían las reparaciones listadas arriba')

    problems = 0
    for image in missing:
        image.delete()
        print(f'  fila #{image.pk} eliminada')
    if missing:
        ok(f'{len(missing)} filas huérfanas eliminadas')

    for product, _count in [] if args.missing_files_only else collect_duplicate_primaries():
        keep = product.images.filter(is_primary=True).order_by('sort_order', 'pk').first()
        product.images.filter(is_primary=True).exclude(pk=keep.pk).update(is_primary=False)
        ok(f'{product.code}: se conservó una sola principal')

    if not args.missing_files_only:
        for product in collect_without_primary():
            first = product.images.order_by('sort_order', 'pk').first()
            if first:
                first.is_primary = True
                first.save(update_fields=['is_primary'])
                ok(f'{product.code}: #{first.pk} ahora es principal')

        storage = ProductImage._meta.get_field('image').storage
        for name in collect_orphan_files():
            try:
                storage.delete(name)
            except OSError as error:
                warn(f'no se pudo borrar {name}: {error}')
                problems += 1

    heading('Resultado')
    if problems:
        fail(f'{problems} archivo(s) no se pudieron borrar; revise bloqueos de Windows')
        return 1
    ok('limpieza aplicada')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
