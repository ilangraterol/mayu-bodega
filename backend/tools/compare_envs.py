"""Compara el catálogo local (ORM) contra un servidor remoto (API).

Por qué existe: ``render.yaml`` versiona ``backend/db.sqlite3`` a propósito, así
que el deploy de producción parte de la copia local de la base. Antes de subir
un cambio de catálogo hay que saber **qué va a reemplazar**: qué artículos,
precios y categorías difieren entre la máquina y el servidor. Sin esto, un push
del ``db.sqlite3`` puede pisar ventas o precios ya cargados en producción sin
que nadie lo note.

Este script es de **solo lectura**: no toca la base local ni la remota.

Compara por ``code`` (la clave estable del artículo), no por ``id``: los ids de
dos bases distintas no tienen por qué coincidir.

Uso::

    ..\\.venv\\Scripts\\python.exe tools\\compare_envs.py --remote https://mayu-bodega.onrender.com

La contraseña sale de ``MAYU_PASSWORD`` o de un prompt interactivo, igual que en
el resto de las herramientas.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    DEFAULT_API_URL,
    api_password,
    api_session,
    fail,
    heading,
    ok,
    request,
    setup_django,
    warn,
)

# Campos que importan para decidir si un push del catálogo pisa datos reales.
CAMPOS_PRODUCTO = (
    'name',
    'barcode',
    'brand',
    'category_name',
    'cost_usd',
    'price_usd',
    'is_active',
)


def _paginar(base: str, token: str, recurso: str, extra: dict | None = None) -> list[dict]:
    """Recorre todas las páginas de un recurso y devuelve las filas."""
    filas: list[dict] = []
    consulta = dict(extra or {})
    url = f'{base}/api/{recurso}/?' + urllib.parse.urlencode(consulta)
    while url:
        estado, cuerpo = request('GET', url, token=token)
        if estado != 200:
            raise SystemExit(f'La API respondió {estado} en {url}:\n  {cuerpo[:300]}')
        pagina = json.loads(cuerpo)
        filas.extend(pagina.get('results', []))
        url = pagina.get('next') or ''
    return filas


def _clave(fila: dict) -> str:
    return str(fila.get('code') or '').strip()


def _norm(valor) -> str:
    """Normaliza para comparar: los Decimal llegan como string con ceros."""
    if valor is None or valor == '':
        return ''
    texto = str(valor).strip()
    try:
        return f'{float(texto):.4f}'
    except ValueError:
        return texto


def _diferencias(local: dict, remoto: dict) -> list[str]:
    cambios = []
    for campo in CAMPOS_PRODUCTO:
        a, b = _norm(local.get(campo)), _norm(remoto.get(campo))
        if a != b:
            cambios.append(f'{campo}: local={local.get(campo)!r} remoto={remoto.get(campo)!r}')
    return cambios


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--remote',
        default=DEFAULT_API_URL,
        help='URL del servidor remoto (por defecto MAYU_API_URL o local).',
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=25,
        help='Máximo de diferencias a listar por bloque (por defecto 25).',
    )
    args = parser.parse_args()

    setup_django()

    from catalog.models import Category, Product
    from core.management.commands.seed_demo import CATEGORIES as SEED_CATEGORIES
    from core.management.commands.seed_demo import PRODUCTS as SEED_PRODUCTS

    remoto = args.remote.rstrip('/')

    # ------------------------------------------------------------------
    heading(f'Conectando con {remoto}')
    # `api_session` resuelve la contraseña sola; solo hay que asegurarse de que
    # quede disponible como variable de entorno en esta llamada.
    os.environ.setdefault('MAYU_PASSWORD', api_password())
    try:
        base, token = api_session(remoto)
        ok('login correcto')
    except SystemExit as error:
        fail(str(error))
        raise SystemExit(1) from error

    # ------------------------------------------------------------------
    heading('1. Conteos')
    locales = list(Product.objects.all())
    remotos = _paginar(base, token, 'products', {'include_inactive': 'true'})
    loc_activos = sum(1 for p in locales if p.is_active)
    rem_activos = sum(1 for p in remotos if p.get('is_active'))
    print(f'  local : {len(locales)} artículos ({loc_activos} activos, {len(locales) - loc_activos} inactivos)')
    print(f'  remoto: {len(remotos)} artículos ({rem_activos} activos, {len(remotos) - rem_activos} inactivos)')
    print(f'  local : {Category.objects.count()} categorías')
    rem_cats = _paginar(base, token, 'categories', {'include_inactive': 'true'})
    print(f'  remoto: {len(rem_cats)} categorías')

    # ------------------------------------------------------------------
    heading('2. ¿Está aplicada la limpieza del seed (commit 950d5c0)?')
    nombres_seed = {c['name'] for c in SEED_CATEGORIES}
    cats_seed_remotas = sorted({c['name'] for c in rem_cats} & nombres_seed)
    if cats_seed_remotas:
        fail(
            'El remoto TODAVÍA tiene categorías del seed: el redespliegue de '
            '950d5c0 no está aplicado.'
        )
        for nombre in cats_seed_remotas:
            warn(nombre)
    else:
        ok('El remoto no muestra categorías del seed: la limpieza sí está aplicada.')

    productos_seed = {p['name'] for p in SEED_PRODUCTS}
    activos_seed_remotos = sorted(
        {p['name'] for p in remotos if p.get('is_active')} & productos_seed
    )
    if activos_seed_remotos:
        fail(f'{len(activos_seed_remotos)} artículo(s) del seed siguen activos en el remoto.')
    else:
        ok('Ningún artículo del seed queda activo en el remoto.')

    # ------------------------------------------------------------------
    heading('3. Artículos por clave (code)')
    por_local = {_clave({'code': p.code}): p for p in locales}
    por_remoto = {_clave(r): r for r in remotos}

    solo_local = sorted(set(por_local) - set(por_remoto))
    solo_remoto = sorted(set(por_remoto) - set(por_local))
    if solo_local:
        warn(f'{len(solo_local)} artículo(s) existen solo en local:')
        for code in solo_local[: args.limit]:
            print(f'      {code} · {por_local[code].name}')
    if solo_remoto:
        warn(f'{len(solo_remoto)} artículo(s) existen solo en remoto:')
        for code in solo_remoto[: args.limit]:
            print(f'      {code} · {por_remoto[code].get("name")}')
    if not solo_local and not solo_remoto:
        ok('Los mismos códigos de artículo existen en ambos entornos.')

    # ------------------------------------------------------------------
    heading('4. Artículos con campos distintos (mismo code)')
    distintos = []
    for code in sorted(set(por_local) & set(por_remoto)):
        local = por_local[code]
        remoto_fila = por_remoto[code]
        local_dict = {
            'name': local.name,
            'barcode': local.barcode,
            'brand': local.brand,
            'category_name': local.category.name if local.category else None,
            'cost_usd': local.cost_usd,
            'price_usd': local.price_usd,
            'is_active': local.is_active,
        }
        cambios = _diferencias(local_dict, remoto_fila)
        if cambios:
            distintos.append((local, cambios))

    if not distintos:
        ok('Ningún artículo en común tiene diferencias de campos.')
    else:
        warn(f'{len(distintos)} artículo(s) en común difieren:')
        for local, cambios in distintos[: args.limit]:
            print(f'      {local.code} · {local.name}')
            for cambio in cambios:
                print(f'          {cambio}')
        if len(distintos) > args.limit:
            print(f'      … y {len(distintos) - args.limit} más (sube --limit para verlos).')

    # ------------------------------------------------------------------
    heading('5. Datos de negocio (lo que se perdería al reemplazar la base)')
    # El catálogo se puede reconstruir; las ventas cobradas y las deudas
    # pendientes no. Por eso se cuentan aparte y con nombre explícito.
    from customers.models import Customer
    from inventory.models import GoodsEntry, StockMovement
    from sales.models import CustomerDebt, DebtPayment, Sale

    negocio = (
        ('clientes', Customer.objects.count(), 'customers', {}),
        ('ventas', Sale.objects.count(), 'sales', {}),
        ('deudas', CustomerDebt.objects.count(), 'debts', {}),
        ('abonos', DebtPayment.objects.count(), 'debt-payments', {}),
        (
            'movimientos de stock',
            StockMovement.objects.count(),
            'stock-movements',
            {},
        ),
        ('entradas de mercancía', GoodsEntry.objects.count(), 'goods-entries', {}),
    )
    perdidas = []
    for etiqueta, total_local, recurso, extra in negocio:
        try:
            filas = _paginar(base, token, recurso, extra)
        except SystemExit as error:
            warn(f'{etiqueta}: no se pudo leer el remoto ({error})')
            continue
        total_remoto = len(filas)
        marca = 'ok  ' if total_local == total_remoto else 'DIF '
        print(f'  [{marca}] {etiqueta:<22} local={total_local:<5} remoto={total_remoto}')
        if total_local != total_remoto:
            perdidas.append((etiqueta, total_local, total_remoto))

    # ------------------------------------------------------------------
    heading('Resumen')
    if cats_seed_remotas or activos_seed_remotos:
        fail(
            'El remoto todavía tiene rastros del seed. Subir el catálogo local '
            'SÍ cambiaría producción, para bien: haría efectiva la limpieza.'
        )
    if solo_remoto:
        fail(
            'Hay artículos en remoto que no existen en local. Un push del '
            'db.sqlite3 los BORRARÍA de producción.'
        )
    if distintos:
        warn(
            'Hay artículos con datos distintos. Un push del db.sqlite3 '
            'sobrescribiría los valores remotos con los locales.'
        )
    if perdidas:
        fail(
            'DATOS DE NEGOCIO DIFERENTES: un push del db.sqlite3 dejaría en '
            'producción los números de la copia local y perdería lo que el '
            'servidor tenga de más.'
        )
        for etiqueta, local_n, remoto_n in perdidas:
            print(f'      {etiqueta}: local={local_n} remoto={remoto_n}')
    if not (
        cats_seed_remotas
        or activos_seed_remotos
        or solo_remoto
        or distintos
        or perdidas
    ):
        ok('Local y remoto coinciden: no hay riesgo al subir el catálogo.')


if __name__ == '__main__':
    main()
