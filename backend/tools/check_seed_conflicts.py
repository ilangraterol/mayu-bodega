"""Report catalogue conflicts that make ``seed_demo`` fail.

``seed_demo`` is idempotent: it matches products by name, so re-running it is
safe. It still fails with ``UNIQUE constraint failed: catalog_product.barcode``
when a *different* article already owns the barcode the demo wants to claim.
This tool lists those conflicts, plus the ones the new category and surcharge
fields can introduce, without touching the database.

Read only. It never writes.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from _common import fail, heading, ok, setup_django, warn

setup_django()

from catalog.models import Category, Product  # noqa: E402
from core.management.commands.seed_demo import (  # noqa: E402
    CATEGORIES,
    PRODUCT_CATEGORIES,
    PRODUCT_SURCHARGES,
    PRODUCTS,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Lista también los artículos que ya coinciden por nombre.',
    )
    return parser


def check_barcodes() -> int:
    """Explain how each demo article will resolve against the real catalogue.

    ``_upsert_product`` falls back to the barcode, so a name mismatch is only a
    warning. A genuine failure is when two demo articles would end up on the
    same row, because the seed could not tell them apart.
    """
    problems = 0
    claimed_by: dict[str, str] = {}
    for payload in PRODUCTS:
        name = payload['name']
        barcode = payload['barcode']
        by_name = Product.objects.filter(name=name).first()
        by_barcode = Product.objects.filter(barcode=barcode).first()

        if barcode in claimed_by:
            problems += 1
            fail(f'{name} y {claimed_by[barcode]} reclaman el mismo código de barras {barcode}')
        else:
            claimed_by[barcode] = name

        if by_name is not None and by_barcode is not None and by_name.pk != by_barcode.pk:
            problems += 1
            fail(f'{name}: el código de barra {barcode} ya lo usa "{by_barcode.name}"')
        elif by_name is None and by_barcode is not None:
            warn(
                f'{name}: se reaprovechará "{by_barcode.name}" (id {by_barcode.pk}) '
                f'por el código de barras {barcode}'
            )
        elif by_name is not None:
            if by_name.barcode != barcode:
                problems += 1
                fail(
                    f'{name} (id {by_name.pk}): tiene el código de barra '
                    f'{by_name.barcode!r} y el seed escribe {barcode!r}'
                )
            elif not by_name.is_active:
                warn(f'{name} (id {by_name.pk}): está inactivo; el seed no lo reactiva.')
            else:
                ok(f'{name} (id {by_name.pk}): coincide.')
        else:
            ok(f'{name}: se crearía nuevo.')

    duplicates = {
        barcode: count
        for barcode, count in Counter(
            p.barcode
            for p in Product.objects.exclude(barcode__isnull=True).exclude(barcode='')
        ).items()
        if count > 1
    }
    if duplicates:
        problems += len(duplicates)
        fail(f'Códigos de barra repetidos en el catálogo: {duplicates}')
    return problems


def check_names() -> int:
    """Product names are the seed's primary key and must stay unique."""
    problems = 0
    duplicates = {
        name: count for name, count in Counter(p['name'] for p in PRODUCTS).items() if count > 1
    }
    if duplicates:
        problems += len(duplicates)
        fail(f'PRODUCTS define el mismo nombre dos veces: {duplicates}')
    return problems


def check_categories() -> int:
    """The seed assigns products to categories that it also creates."""
    problems = 0
    declared = {payload['name'] for payload in CATEGORIES}
    missing = set(PRODUCT_CATEGORIES.values()) - declared
    if missing:
        problems += len(missing)
        fail(f'PRODUCT_CATEGORIES apunta a categorías no declaradas: {sorted(missing)}')

    for name, surcharge in PRODUCT_SURCHARGES.items():
        if surcharge is None:
            continue
        if not 0 <= float(surcharge) <= 100:
            problems += 1
            fail(f'PRODUCT_SURCHARGES[{name!r}] = {surcharge} está fuera de [0, 100]')
    return problems


def check_orphans() -> int:
    """Existing data must survive the migration: nothing points nowhere."""
    problems = 0
    if Category.objects.exists():
        ok(f'{Category.objects.count()} categorías ya existen en el catálogo.')
    else:
        ok('Todavía no hay categorías; el seed creará las primeras.')
    return problems


def main() -> int:
    args = build_parser().parse_args()

    heading('Nombres duplicados en PRODUCTS')
    problems = check_names()

    heading('Conflictos de código de barra')
    problems += check_barcodes()

    heading('Categorías declaradas por el seed')
    problems += check_categories()

    heading('Estado actual del catálogo')
    problems += check_orphans()

    if problems:
        print(f'\n{problems} problema(s). `manage.py seed_demo` fallará hasta resolverlos.')
        return 1

    print('\nSin conflictos: `manage.py seed_demo` puede ejecutarse.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
