"""Audita qué dejó el ``manage.py seed_demo`` dentro de un catálogo real.

Por qué existe: ``seed_demo._upsert_product`` no solo crea artículos. Si un
artículo del catálogo real ya ocupa el código de barras que el seed quiere usar,
lo **reutiliza y le sobrescribe** precio, costo, marca, unidad y categoría::

    existing = Product.objects.filter(name=name).first()
    if existing is None and data.get('barcode'):
        existing = Product.objects.filter(barcode=data['barcode']).first()
    ...
    for field, value in data.items():
        setattr(existing, field, value)

Es decir, un catálogo con "Aceite vegetal Girasol 1L" real puede acabar con el
precio y la categoría del artículo de demostración. Esto NO es una operación
reversible sin respaldo, así que antes de borrar nada conviene saber qué quedó
tocado.

Este script es de **solo lectura**. Imprime tres grupos:

1. Artículos que el seed probablemente creó (nombre y código de barras propios).
2. Artículos reales cuyos campos quedaron igualados a los del seed. Aquí se
   comparan los valores actuales contra los declarados en ``seed_demo`` para
   mostrar la diferencia.
3. Filas de las que el seed es responsable: categorías, clientes, ventas, deudas,
   abonos y movimientos de inventario.

Para reparar, mira ``--help`` de las herramientas vecinas antes de escribir un
script nuevo; ninguna de las existentes borra artículos.
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    fail,
    heading,
    ok,
    setup_django,
    warn,
)


def _fmt(value) -> str:
    if value is None:
        return 'hereda/None'
    if isinstance(value, Decimal):
        return f'{value}'
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Muestra los campos de cada artículo tocado, no solo el resumen.',
    )
    args = parser.parse_args()

    setup_django()

    from catalog.models import Category, Product
    from core.management.commands.seed_demo import (
        CATEGORIES,
        CUSTOMERS,
        PRODUCTS,
        PRODUCT_CATEGORIES,
    )
    from customers.models import Customer
    from inventory.models import StockMovement
    from sales.models import CustomerDebt, DebtPayment, Sale, SaleItem

    # ------------------------------------------------------------------
    heading('1. Artículos Propios del seed (creados por seed_demo)')
    seed_names = {p['name'] for p in PRODUCTS}
    seed_barcodes = {p['barcode'] for p in PRODUCTS}
    propios = Product.objects.filter(name__in=seed_names)
    if not propios:
        ok('Ninguno: el seed no creó artículos con su propio nombre.')
    for p in propios.order_by('id'):
        nuevo = p.id > max(
            [q.id for q in Product.objects.exclude(name__in=seed_names)] or [0]
        )
        marca = 'probablemente creado por el seed' if nuevo else 'preexistente'
        warn(f'id {p.id} · {p.name} · {p.barcode} · {marca}')

    # ------------------------------------------------------------------
    heading('2. Artículos REALES sobrescritos por el seed (peli Greatest)')
    overwritten = []
    for payload in PRODUCTS:
        real = (
            Product.objects.filter(barcode=payload['barcode'])
            .exclude(name=payload['name'])
            .first()
        )
        if real is None:
            continue
        esperado = {
            'brand': payload['brand'],
            'unit_of_measure': payload['unit_of_measure'],
            'cost_usd': Decimal(payload['cost_usd']),
            'price_usd': Decimal(payload['price_usd']),
        }
        cat_demo = PRODUCT_CATEGORIES.get(payload['name'])
        cat_real = real.category.name if real.category else None
        cat_esperada = cat_demo if cat_demo == cat_real else f'{cat_demo} (seed)'
        diferencias = [
            f'{campo}: {_fmt(getattr(real, campo))} vs {_fmt(esperado_valor)}'
            for campo, esperado_valor in esperado.items()
            if getattr(real, campo) != esperado_valor
        ]
        if cat_demo and cat_real != cat_demo:
            diferencias.append(f'category: {_fmt(cat_real)} vs {_fmt(cat_esperada)}')
        overwritten.append((real, payload, diferencias))

    if not overwritten:
        ok('Ningún artículo real comparte código de barras con el seed.')
    for real, payload, diferencias in overwritten:
        fail(
            f'id {real.id} · "{real.name}" absorbió el artículo demo '
            f'"{payload["name"]}" (código {payload["barcode"]})'
        )
        for diferencia in diferencias:
            warn(f'    {diferencia}')
        if args.verbose and not diferencias:
            ok('    sus valores coinciden con los del seed (igualmente tocado)')

    # ------------------------------------------------------------------
    heading('3. Filas de las que el seed es responsable')
    cat_seed = {c['name'] for c in CATEGORIES}
    docs_seed = {c['document_id'] for c in CUSTOMERS}
    nuevas_cats = list(Category.objects.filter(name__in=cat_seed))
    nuevas_clientes = list(Customer.objects.filter(document_id__in=docs_seed))
    ok(f'Categorías del seed presentes: {len(nuevas_cats)}')
    for c in nuevas_cats:
        propios_cat = c.products.count()
        warn(f'    {c.name} · surcharge {_fmt(c.surcharge_percentage)} · {propios_cat} artículos')
    ok(f'Clientes del seed presentes: {len(nuevas_clientes)}')
    for c in nuevas_clientes:
        warn(f'    {c.document_id} · {c.name}')
    ok(f'Ventas totales: {Sale.objects.count()} (items: {SaleItem.objects.count()})')
    ok(f'Deudas: {CustomerDebt.objects.count()} · abonos: {DebtPayment.objects.count()}')
    ok(f'Movimientos de inventario: {StockMovement.objects.count()}')
    ok(f'Artículos totales: {Product.objects.count()} · sin categoría: '
       f'{Product.objects.filter(category__isnull=True).count()}')

    # ------------------------------------------------------------------
    heading('Resumen')
    if overwritten:
        fail(
            f'{len(overwritten)} artículo(s) real(es) quedaron con precio/costo/'
            'categoría del seed. Sin respaldo previo NO se pueden recuperar solos.'
        )
    else:
        ok('Ningún artículo real fue sobrescrito.')


if __name__ == '__main__':
    main()
