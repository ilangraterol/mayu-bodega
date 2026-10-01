"""Quita del catalogo los artefactos que creo ``manage.py seed_demo``.

Por que existe: ``seed_demo`` no solo agrega filas, tambien invade el catalogo
real. ``_upsert_product`` busca por nombre y luego por codigo de barras, asi que
si un articulo real ya ocupa el codigo que el seed quiere usar, lo reutiliza y le
pisa precio, costo, marca, unidad y categoria. Ademas crea articulos y categorias
que el negocio nunca pidio.

Este script NO intenta adivinar ni reconstruir los valores originales (no hay
respaldo previo). Solo hace lo que es seguro:

* **Categorias del seed**: se eliminan. ``Product.category`` es ``PROTECT``, asi
  que primero se suelta la referencia de cada articulo y luego se borra la
  categoria. Solo depende de ellas los articulos, por eso no hay mas que romper.
* **Articulos del seed**: se **desactivan** (``is_active = False``), no se borran.
  Todos tienen movimientos de inventario y ``StockMovement.product`` es
  ``PROTECT``: borrarlos dispararia el protect, y la regla del dominio es que el
  historial de movimientos es inmutable. Desactivarlos los saca del catalogo, de
  la API y del punto de venta sin destruir la auditoria.

Como se decide que es "del seed": el propio script calcula el limite. El catalogo
real son los ids anteriores a los que el seed genero, asi que toma el id maximo
de los articulos cuyo codigo de barras NO aparece en ``seed_demo.PRODUCTS``. Para
las categorias hace lo mismo con los nombres de ``seed_demo.CATEGORIES``. Asi una
categoria que el negocio creo antes --"Bebidas", por ejemplo-- nunca se toca,
aunque el seed tambien la haya listado.

Los precios pisados por el seed (4 articulos reales) NO se restauran aqui: no hay
respaldo. El script solo los lista al final para que se corregan desde la app.

Solo informe por defecto. Pass ``--apply`` para escribir.
"""

from __future__ import annotations

import argparse
import sys

from django.db.models import Max

from _common import fail, heading, ok, require_apply, setup_django, warn

setup_django()

from catalog.models import Category, Product  # noqa: E402
from core.management.commands.seed_demo import (  # noqa: E402
    CATEGORIES,
    PRODUCTS,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Escribe los cambios. Sin este flag solo imprime el plan.',
    )
    parser.add_argument(
        '--only',
        choices=['all', 'categories', 'products'],
        default='all',
        help='Acota la limpieza. Por defecto hace ambas cosas.',
    )
    return parser


def find_seed_categories() -> tuple[list[Category], int | None]:
    """Categorias creadas por el seed, segun el limite que calcula la base."""
    seed_names = {c['name'] for c in CATEGORIES}
    baseline = (
        Category.objects.exclude(name__in=seed_names)
        .aggregate(bound=Max('id'))['bound']
    )
    if baseline is None:
        return list(Category.objects.filter(name__in=seed_names)), None
    return list(Category.objects.filter(id__gt=baseline, name__in=seed_names)), baseline


def find_seed_products() -> tuple[list[Product], int | None]:
    """Articulos creados por el seed, segun el limite que calcula la base."""
    seed_barcodes = {p['barcode'] for p in PRODUCTS}
    baseline = (
        Product.objects.exclude(barcode__in=seed_barcodes)
        .aggregate(bound=Max('id'))['bound']
    )
    if baseline is None:
        return list(Product.objects.filter(barcode__in=seed_barcodes)), None
    return list(Product.objects.filter(id__gt=baseline, barcode__in=seed_barcodes)), baseline


def report_pisados() -> None:
    """Lista los articulos reales que el seed absorbio por codigo de barras."""
    pisados = []
    for payload in PRODUCTS:
        real = (
            Product.objects.filter(barcode=payload['barcode'])
            .exclude(name=payload['name'])
            .first()
        )
        if real is not None:
            pisados.append((real, payload))
    if not pisados:
        return
    warn('')
    warn(f'PRECIO/COSTO PISADOS por el seed, sin respaldo (id -> nombre):')
    for real, payload in pisados:
        print(
            f'    id {real.pk:>4} · {real.name} · costo {real.cost_usd} '
            f'precio {real.price_usd}  (lo del seed era de "{payload["name"]}")'
        )
    warn('    Corregilos desde la app: el script no inventa precios.')


def main() -> int:
    args = build_parser().parse_args()
    categorias, cat_base = find_seed_categories()
    productos, prod_base = find_seed_products()

    heading('Plan de limpieza del catalogo')
    ok(f'Base real detectada: categorias hasta id {cat_base}, articulos hasta id {prod_base}.')

    if args.only in {'all', 'categories'}:
        print('\n1. Categorias del seed a eliminar (yarticles que quedaran sin categoria):')
        if not categorias:
            ok('   ninguna')
        for categoria in categorias:
            print(f'   - {categoria.name} (id {categoria.pk})')
            for p in categoria.products.order_by('id'):
                print(f'       queda sin categoria: id {p.pk} · {p.name}')

    if args.only in {'all', 'products'}:
        print('\n2. Articulos del seed a DESACTIVAR (no se borran: tienen movimientos):')
        if not productos:
            ok('   ninguno')
        for p in productos:
            movs = p.movements.count()
            print(f'   - id {p.pk} · {p.name} · {movs} movimiento(s) de inventario')

    if args.only in {'all', 'categories'}:
        report_pisados()

    if not args.apply:
        warn('\nSolo informe. Vuelva a ejecutar con --apply para escribir los cambios.')
        return 1

    require_apply(args.apply, 'limpiar el catalogo de artefactos de seed_demo')

    if args.only in {'all', 'categories'}:
        for categoria in categorias:
            afectados = list(categoria.products.all())
            categoria.products.update(category=None)
            ok(f'Suelta la categoria de {len(afectados)} articulo(s) de "{categoria.name}".')
            categoria.delete()
            ok(f'Categoria "{categoria.name}" eliminada.')

    if args.only in {'all', 'products'}:
        for p in productos:
            if p.is_active:
                p.is_active = False
                p.save(update_fields=['is_active'])
            ok(f'id {p.pk} "{p.name}" desactivado.')

    heading('Resultado')
    ok(f'Categorias: {Category.objects.count()} · articulos: {Product.objects.count()} '
       f'(activos {Product.objects.filter(is_active=True).count()})')
    print('\nLimpieza aplicada. Revisa los precios pisados que se listaron arriba.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
