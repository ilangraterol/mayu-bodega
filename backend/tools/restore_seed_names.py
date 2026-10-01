"""Restore article names that ``seed_demo`` shortened.

The demo catalogue ships short generic names ("Azucar 1kg"). When the real
catalogue already owns the barcode, the seed reuses that row. An earlier version
of the seed also overwrote its name, which erased descriptive real names such as
"Aztcar Bugalu 1kg". This tool reports the products whose name matches a demo
name but whose brand says otherwise, and puts the descriptive name back.

Read only by default. Pass ``--apply`` to rename.
"""

from __future__ import annotations

import argparse
import sys

from _common import fail, heading, ok, require_apply, setup_django, warn

setup_django()

from catalog.models import Product  # noqa: E402

# demo name -> the descriptive name the catalogue used before the seed ran.
RENAMES = {
    'Aceite vegetal 1L': 'Aceite vegetal Girasol 1L',
    'Azúcar 1kg': 'Azúcar Bugalú 1kg',
    'Pasta corta 500g': 'Pasta corta Doria 500g',
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Escribe los nombres restaurados. Sin este flag solo se informa.',
    )
    return parser


def collect():
    """Products that still carry a demo name and are safe to rename back."""
    targets = []
    for demo_name, real_name in RENAMES.items():
        product = Product.objects.filter(name=demo_name).first()
        if product is None:
            continue
        if Product.objects.filter(name=real_name).exclude(pk=product.pk).exists():
            fail(f'{demo_name}: ya existe "{real_name}"; no se renombra para evitar duplicados.')
            continue
        targets.append((product, demo_name, real_name))
    return targets


def main() -> int:
    args = build_parser().parse_args()
    targets = collect()

    heading('Plan de restauración de nombres')
    if not targets:
        ok('No hay artículos con nombres de demostración que restaurar.')
        return 0

    for product, demo_name, real_name in targets:
        print(f'  id {product.pk:>4} · "{demo_name}" -> "{real_name}" (marca: {product.brand})')

    if not args.apply:
        warn('Solo informe. Vuelva a ejecutar con --apply para escribir los cambios.')
        return 1

    require_apply(args.apply, f'renombrar {len(targets)} artículo(s)')
    for product, _demo_name, real_name in targets:
        product.name = real_name
        product.save(update_fields=['name'])
        ok(f'id {product.pk}: ahora es "{real_name}"')

    print(f'\n{len(targets)} artículo(s) restaurados.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
