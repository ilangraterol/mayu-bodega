"""Inspect a single stored photo: format, size, dimensions and file locks.

Read only. This is the tool to reach for when Pillow or Windows file locking is
suspected, because it reports whether the file can still be opened, read and
closed without leaving a handle behind.

    python tools/inspect_image.py --product P000011
    python tools/inspect_image.py --image-id 45
    python tools/inspect_image.py --product P000011 --check-webp
"""

import argparse
import os

from _common import fail, heading, ok, setup_django, warn

setup_django()

from catalog.models import Product, ProductImage  # noqa: E402


def describe(label: str, field) -> bool:
    if not field:
        print(f'  {label:<10} (vacío)')
        return False

    storage, name = field.storage, field.name
    if not storage.exists(name):
        fail(f'{label}: {name} no existe en el almacenamiento')
        return False

    size = storage.size(name)
    try:
        from PIL import Image

        with storage.open(name, 'rb') as handle:
            with Image.open(handle) as image:
                image.load()
                print(
                    f'  {label:<10} {image.format} {image.width}x{image.height} '
                    f'modo={image.mode} {size} bytes'
                )
                return image.format == 'WEBP'
    except Exception as error:  # noqa: BLE001 - diagnostic tool reports anything
        fail(f'{label}: no se pudo abrir ({error})')
        return False


def lock_check(image_row) -> None:
    """Open and close every field, then confirm the file is still deletable."""
    for label, field in (('image', image_row.image), ('thumbnail', image_row.thumbnail)):
        if not field or not field.storage.exists(field.name):
            continue
        name, storage = field.name, field.storage
        try:
            with storage.open(name, 'rb') as handle:
                handle.read(1024)
        except OSError as error:
            fail(f'{label}: no se pudo leer ({error})')
            continue
        try:
            probe = storage.path(name)
        except (NotImplementedError, AttributeError):
            ok(f'{label}: legible (almacenamiento remoto, sin prueba de bloqueo)')
            continue
        if os.path.exists(probe):
            try:
                os.rename(probe, probe + '.probe')
                os.rename(probe + '.probe', probe)
                ok(f'{label}: sin handle abierto, se puede renombrar')
            except OSError as error:
                fail(f'{label}: bloqueado en Windows ({error})')
        else:
            warn(f'{label}: el archivo desapareció durante la comprobación')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--product', help='código de producto, por ejemplo P000011')
    group.add_argument('--image-id', type=int, help='id de la fila ProductImage')
    parser.add_argument('--check-webp', action='store_true', help='advertir si no es WebP')
    args = parser.parse_args()

    rows = ProductImage.objects.select_related('product').order_by('pk')
    if args.product:
        product = Product.objects.filter(code=args.product).first()
        if product is None:
            fail(f'no existe el producto {args.product}')
            return 1
        rows = rows.filter(product=product)
    else:
        rows = rows.filter(pk=args.image_id)

    if not rows.exists():
        fail('no hay filas de imagen para ese criterio')
        return 1

    problems = 0
    for row in rows:
        heading(f'#{row.pk} {row.product.code} - {row.product.name}')
        print(f'  principal : {row.is_primary}')
        print(f'  creado    : {row.created_at:%Y-%m-%d %H:%M}')
        print(f'  tamaño    : {row.size_bytes} bytes (registro) {row.width}x{row.height}')
        if not describe('image', row.image):
            problems += 1
        if not describe('thumbnail', row.thumbnail):
            problems += 1
        lock_check(row)

    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
