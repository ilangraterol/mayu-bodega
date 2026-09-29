"""Import a curated catalogue of bodega staples from the Cost Azul price list.

Cost Azul (https://costazul.sigo.com.ve) publishes a public retail price list but
no purchase cost, no stock and no barcodes. This import therefore only ever sets
the retail price: ``cost_usd`` stays at zero until real merchandise is received,
and stock stays at zero until a ``GoodsEntry`` or an ``ExitNote`` moves it.

The selection lives in ``costazul_manifest.json`` so it can be reviewed and
edited as data rather than code. Every entry is keyed by the site's own product
id in ``source_ref``, which makes the command idempotent: re-running it refreshes
names and prices instead of duplicating the catalogue.
"""

import html
import json
import re
import time
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.image_processing import MAX_UPLOAD_BYTES
from catalog.models import UNIT_UNIDAD, Product, ProductImage
from core.money import MONEY_PLACES, quantize_money

MANIFEST_PATH = Path(__file__).with_name('costazul_manifest.json')
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/125.0 Safari/537.36'
)
BASE_CURRENCY = 'USD'

NAME_RE = re.compile(r'<h1[^>]*itemprop="name"[^>]*>(?P<name>.*?)</h1>', re.S)
PRICE_RE = re.compile(r'itemprop="price"[^>]*content="(?P<price>[0-9]+(?:[.,][0-9]+)?)"')
CURRENCY_RE = re.compile(r'itemprop="priceCurrency"[^>]*content="(?P<currency>[A-Za-z]{3})"')
IMAGE_RE = re.compile(r'data-full-image-url="(?P<url>[^"]+)"')


class SourceError(Exception):
    """A product page could not be read as a usable catalogue entry."""


def clean_text(value: str) -> str:
    return re.sub(r'\s+', ' ', html.unescape(value)).strip()


def parse_money(raw: str) -> Decimal:
    """Accept both ``0.65`` and ``0,65`` without ever touching binary floats."""
    text = raw.strip().replace(' ', '')
    if ',' in text and '.' in text:
        text = text.replace(',', '')
    elif ',' in text:
        text = text.replace(',', '.')
    try:
        return quantize_money(Decimal(text))
    except (InvalidOperation, ValueError) as error:
        raise SourceError(f'precio ilegible: {raw!r}') from error


def read_product_page(url: str, timeout: int = 45) -> dict:
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            page = response.read().decode('utf-8', errors='replace')
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise SourceError(f'no se pudo descargar: {error}') from error

    name_match = NAME_RE.search(page)
    price_match = PRICE_RE.search(page)
    if not name_match or not price_match:
        raise SourceError('la pagina no tiene nombre o precio en el formato esperado')

    currency_match = CURRENCY_RE.search(page)
    currency = currency_match.group('currency').upper() if currency_match else ''
    if currency != BASE_CURRENCY:
        # The site can be switched to bolivars. Importing that into price_usd
        # would silently corrupt every amount, so refuse instead.
        raise SourceError(f'moneda inesperada: {currency or "desconocida"} (se exige {BASE_CURRENCY})')

    price = parse_money(price_match.group('price'))
    if price <= 0:
        raise SourceError(f'precio no utilizable: {price}')

    image_match = IMAGE_RE.search(page)
    return {
        'name': clean_text(name_match.group('name')),
        'price': price,
        'image_url': image_match.group('url') if image_match else None,
    }


def download(url: str, timeout: int = 45) -> bytes:
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise SourceError(f'no se pudo descargar la imagen: {error}') from error


class Command(BaseCommand):
    help = 'Importa el catalogo curado de Cost Azul con sus fotografias.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Consulta el sitio y muestra el plan sin escribir en la base de datos.',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=1.0,
            help='Pausa entre peticiones al sitio, en segundos (por defecto 1.0).',
        )
        parser.add_argument(
            '--family',
            action='append',
            dest='families',
            help='Limita la importacion a una familia. Se puede repetir.',
        )
        parser.add_argument(
            '--skip-images',
            action='store_true',
            help='No descarga fotografias.',
        )
        parser.add_argument(
            '--refresh-images',
            action='store_true',
            help='Vuelve a descargar la foto de los productos que ya tienen una.',
        )

    def handle(self, *args, **options):
        entries = self._load_manifest()
        if options['families']:
            wanted = {name.strip().lower() for name in options['families']}
            entries = [entry for entry in entries if entry['family'].strip().lower() in wanted]
            if not entries:
                raise CommandError(
                    f'Ningun producto coincide con {sorted(wanted)}. '
                    f'Familias disponibles: {", ".join(sorted(self._families(self._load_manifest())))}'
                )

        dry_run = options['dry_run']
        delay = max(float(options['delay']), 0.0)
        style = self.style.SUCCESS if not dry_run else self.style.WARNING

        self.stdout.write(
            f'Cost Azul: {len(entries)} productos'
            f'{" (dry-run, no se escribe nada)" if dry_run else ""}'
        )

        created_count = updated_count = failed_count = 0
        for index, entry in enumerate(entries, start=1):
            prefix = f'[{index}/{len(entries)}] {entry["family"]} / {entry["brand"]}'
            try:
                listing = read_product_page(entry['url'])
                image_bytes = None
                if not options['skip_images'] and listing['image_url']:
                    image_bytes = download(listing['image_url'])
                    if len(image_bytes) > MAX_UPLOAD_BYTES:
                        self.stderr.write(
                            f'{prefix}: imagen de {len(image_bytes)} B descartada, '
                            f'supera el maximo permitido'
                        )
                        image_bytes = None
            except SourceError as error:
                failed_count += 1
                self.stderr.write(self.style.ERROR(f'{prefix}: {error}'))
                self._pause(delay)
                continue

            if dry_run:
                verdict = 'nuevo' if not self._existing(entry) else 'actualizar'
                self.stdout.write(
                    f'{prefix}: {listing["name"][:52]} | {listing["price"]} USD'
                    f' | foto {"si" if image_bytes else "no"} | {verdict}'
                )
                self._pause(delay)
                continue

            product, created = self._upsert(entry, listing)
            if created:
                created_count += 1
            else:
                updated_count += 1

            photo = 'omitida'
            if image_bytes and (options['refresh_images'] or not product.images.exists()):
                self._attach_image(product, entry, image_bytes)
                photo = 'guardada'
            elif product.images.exists():
                photo = 'ya tenia'

            self.stdout.write(
                style(
                    f'{prefix}: {"+" if created else "~"} {product.code} '
                    f'{listing["price"]} USD | foto {photo} | {listing["name"][:44]}'
                )
            )
            self._pause(delay)

        self.stdout.write(
            f'\nResumen: {created_count} creados, {updated_count} actualizados, '
            f'{failed_count} fallidos'
            + (' (dry-run)' if dry_run else '')
        )
        if failed_count:
            raise CommandError(f'{failed_count} productos no se pudieron importar.')

    def _pause(self, delay: float) -> None:
        if delay:
            time.sleep(delay)

    def _load_manifest(self) -> list[dict]:
        if not MANIFEST_PATH.exists():
            raise CommandError(f'No se encontro el manifiesto {MANIFEST_PATH}')
        with MANIFEST_PATH.open(encoding='utf-8') as handle:
            entries = json.load(handle)
        if not isinstance(entries, list) or not entries:
            raise CommandError('El manifiesto esta vacio.')
        for entry in entries:
            for field in ('source', 'source_ref', 'url', 'family', 'brand'):
                if not entry.get(field):
                    raise CommandError(f'Entrada incompleta en el manifiesto: {entry}')
        return entries

    def _families(self, entries: list[dict]) -> set[str]:
        return {entry['family'] for entry in entries}

    def _existing(self, entry: dict) -> Product | None:
        return Product.objects.filter(
            source=entry['source'], source_ref=entry['source_ref']
        ).first()

    def _upsert(self, entry: dict, listing: dict) -> tuple[Product, bool]:
        """Create or refresh a product, never touching local cost or stock.

        ``cost_usd`` and ``stock`` belong to the shop: re-running the import
        after the first load must not wipe the prices paid or the units counted.
        """
        with transaction.atomic():
            product = self._existing(entry)
            if product is None:
                return (
                    Product.objects.create(
                        name=listing['name'][:255],
                        brand=entry['brand'][:120],
                        unit_of_measure=UNIT_UNIDAD,
                        units_per_package=1,
                        cost_usd=Decimal('0.00'),
                        price_usd=listing['price'],
                        is_active=True,
                        source=entry['source'],
                        source_ref=entry['source_ref'],
                        notes=(
                            f'Importado de {entry["url"]} '
                            f'(familia: {entry["family"]}). '
                            f'Costo y stock pendientes de carga real.'
                        ),
                    ),
                    True,
                )
            product.name = listing['name'][:255]
            product.price_usd = listing['price']
            product.save(update_fields=['name', 'price_usd', 'updated_at'])
            return product, False

    def _attach_image(self, product: Product, entry: dict, image_bytes: bytes) -> None:
        with transaction.atomic():
            product.images.all().delete()
            filename = f'{product.code}.jpeg'
            ProductImage.objects.create(
                product=product,
                image=ContentFile(image_bytes, name=filename),
                original_filename=Path(entry['url']).name[:255] or filename,
                is_primary=True,
            )
