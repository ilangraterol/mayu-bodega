"""Product catalogue.

One ``Product`` row per commercial article. Presentation changes (a pack, a
bulto) do not create a new product: they are expressed through
``units_per_package``, the number of internal units contained in a pack/bulto
used when receiving merchandise in bulk.

``Category`` groups articles and carries a shared surcharge. Both the category
and the article expose a nullable ``surcharge_percentage``: ``None`` means
"inherit the level above", which is what makes the article > category > store
resolution in :mod:`catalog.surcharge` work.
"""

from decimal import Decimal
from pathlib import Path

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction

from catalog.image_processing import (
    IMAGE_MAX_SIDE,
    THUMBNAIL_MAX_SIDE,
    build_upload_path,
    process_product_image,
    process_product_thumbnail,
)
from catalog.surcharge import SURCHARGE_MAX_PERCENT, SURCHARGE_MIN_PERCENT
from core.money import MONEY_PLACES, QUANTITY_PLACES, RATE_PLACES, quantize_quantity

UNIT_UNIDAD = 'UNIDAD'
UNIT_PAQUETE = 'PAQUETE'
UNIT_BULTO = 'BULTO'
UNIT_CAJA = 'CAJA'
UNIT_LIBRA = 'LIBRA'
UNIT_KILO = 'KILO'
UNIT_LITRO = 'LITRO'
UNIT_UNIDAD_FISICA = 'UNIDAD_FISICA'

UNIT_OF_MEASURE_CHOICES = [
    (UNIT_UNIDAD, 'Unidad'),
    (UNIT_PAQUETE, 'Paquete'),
    (UNIT_BULTO, 'Bulto'),
    (UNIT_CAJA, 'Caja'),
    (UNIT_LIBRA, 'Libra'),
    (UNIT_KILO, 'Kilogramo'),
    (UNIT_LITRO, 'Litro'),
    (UNIT_UNIDAD_FISICA, 'Unidad física'),
]

# Units that express a bulk container holding `units_per_package` internal units.
BULK_UNITS = {UNIT_PAQUETE, UNIT_BULTO, UNIT_CAJA}

# Shared validators for every level that can carry a surcharge. A nullable
# percentage means "inherit", so the minimum/maximum only apply when it is set.
SURCHARGE_VALIDATORS = [
    MinValueValidator(SURCHARGE_MIN_PERCENT),
    MaxValueValidator(SURCHARGE_MAX_PERCENT),
]


class Category(models.Model):
    """A family of articles that shares a name and, optionally, a surcharge."""

    code = models.CharField(max_length=16, unique=True, editable=False)
    name = models.CharField(
        max_length=120,
        unique=True,
        help_text='Nombre de la categoría, por ejemplo "Abarrotes" o "Lácteos".',
    )
    surcharge_percentage = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        default=None,
        validators=SURCHARGE_VALIDATORS,
        verbose_name='Recargo de la categoría (%)',
        help_text='Se aplica a los artículos de la categoría que no tengan recargo propio. Vacío = hereda el recargo de la tienda.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(surcharge_percentage__isnull=True)
                    | (
                        models.Q(surcharge_percentage__gte=SURCHARGE_MIN_PERCENT)
                        & models.Q(surcharge_percentage__lte=SURCHARGE_MAX_PERCENT)
                    )
                ),
                name='category_surcharge_between_0_and_100',
            ),
        ]
        indexes = [models.Index(fields=['name']), models.Index(fields=['is_active'])]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._generate_code()
        return super().save(*args, **kwargs)

    @classmethod
    def _generate_code(cls) -> str:
        last = cls.objects.order_by('-id').values_list('code', flat=True).first()
        sequence = 0
        if last and last.startswith('C'):
            try:
                sequence = int(last[1:])
            except ValueError:
                sequence = 0
        candidate = f'C{sequence + 1:04d}'
        while cls.objects.filter(code=candidate).exists():
            sequence += 1
            candidate = f'C{sequence + 1:04d}'
        return candidate


class ProductQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def with_stock(self):
        return self.annotate(models.F('stock'))

    def sellable(self):
        return self.filter(is_active=True)


class Product(models.Model):
    code = models.CharField(max_length=32, unique=True, editable=False)
    barcode = models.CharField(max_length=64, unique=True, null=True, blank=True)
    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=120, blank=True, default='')
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='products',
        verbose_name='Categoría',
    )
    surcharge_percentage = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        default=None,
        validators=SURCHARGE_VALIDATORS,
        verbose_name='Recargo del artículo (%)',
        help_text='Recargo propio del artículo. Vacío = hereda el de su categoría, o el de la tienda si tampoco tiene categoría.',
    )
    unit_of_measure = models.CharField(
        max_length=20,
        choices=UNIT_OF_MEASURE_CHOICES,
        default=UNIT_UNIDAD,
    )
    units_per_package = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text='Unidades internas contenidas en un paquete/bulto para el ingreso de mercancía.',
    )
    cost_usd = models.DecimalField(
        max_digits=12,
        decimal_places=MONEY_PLACES,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Costo de compra (USD)',
    )
    price_usd = models.DecimalField(
        max_digits=12,
        decimal_places=MONEY_PLACES,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Precio de venta (USD)',
    )
    stock = models.DecimalField(
        max_digits=12,
        decimal_places=QUANTITY_PLACES,
        default=Decimal('0.000'),
        validators=[MinValueValidator(Decimal('0.000'))],
        editable=False,
        help_text='Unidades físicamente disponibles (nunca negativo).',
    )
    pending_units = models.DecimalField(
        max_digits=12,
        decimal_places=QUANTITY_PLACES,
        default=Decimal('0.000'),
        validators=[MinValueValidator(Decimal('0.000'))],
        editable=False,
        help_text=(
            'Unidades vendidas sin existencia disponible cuando la tienda permite '
            'vender con stock cero. Las entradas futuras las cancelan primero.'
        ),
    )
    is_active = models.BooleanField(default=True)
    source = models.CharField(
        max_length=40,
        blank=True,
        default='',
        help_text='Origen del alta, por ejemplo "costazul". Vacio cuando es manual.',
    )
    source_ref = models.CharField(
        max_length=64,
        blank=True,
        default='',
        help_text='Identificador estable en el origen, para reimportar sin duplicar.',
    )
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ['name']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(units_per_package__gte=1),
                name='product_units_per_package_gte_1',
            ),
            models.CheckConstraint(
                condition=models.Q(stock__gte=0),
                name='product_stock_gte_0',
            ),
            models.CheckConstraint(
                condition=models.Q(pending_units__gte=0),
                name='product_pending_units_gte_0',
            ),
            models.CheckConstraint(
                condition=models.Q(cost_usd__gte=0) & models.Q(price_usd__gte=0),
                name='product_amounts_gte_0',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(surcharge_percentage__isnull=True)
                    | (
                        models.Q(surcharge_percentage__gte=SURCHARGE_MIN_PERCENT)
                        & models.Q(surcharge_percentage__lte=SURCHARGE_MAX_PERCENT)
                    )
                ),
                name='product_surcharge_between_0_and_100',
            ),
            # One product per external reference, so a re-run of an import
            # updates the existing row instead of duplicating the catalogue.
            models.UniqueConstraint(
                fields=['source', 'source_ref'],
                condition=~models.Q(source=''),
                name='one_product_per_source_ref',
            ),
        ]
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_active']),
            models.Index(fields=['source', 'source_ref']),
        ]

    def __str__(self) -> str:
        return f'{self.code} - {self.name}'

    @property
    def is_bulk_unit(self) -> bool:
        return self.unit_of_measure in BULK_UNITS

    @property
    def net_position(self) -> Decimal:
        """Net units according to the ledger: ``stock - pending_units``.

        The invariant every stock change must preserve is
        ``sum(signed movements) == stock - pending_units``.
        """
        return quantize_quantity((self.stock or Decimal('0')) - (self.pending_units or Decimal('0')))

    @property
    def units_in_one_package(self) -> int:
        return max(int(self.units_per_package or 1), 1)

    @property
    def primary_image(self):
        images = list(self.images.all())
        if not images:
            return None
        for image in images:
            if image.is_primary:
                return image
        return images[0]

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._generate_code()
        return super().save(*args, **kwargs)

    @classmethod
    def _generate_code(cls) -> str:
        last = cls.objects.order_by('-id').values_list('code', flat=True).first()
        sequence = 0
        if last and last.startswith('P'):
            try:
                sequence = int(last[1:])
            except ValueError:
                sequence = 0
        candidate = f'P{sequence + 1:06d}'
        while cls.objects.filter(code=candidate).exists():
            sequence += 1
            candidate = f'P{sequence + 1:06d}'
        return candidate


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=build_upload_path, max_length=255)
    thumbnail = models.ImageField(upload_to=build_upload_path, max_length=255, blank=True)
    original_filename = models.CharField(max_length=255, blank=True, default='')
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    size_bytes = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', 'sort_order', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['product'],
                condition=models.Q(is_primary=True),
                name='one_primary_image_per_product',
            ),
        ]
        indexes = [
            models.Index(fields=['product', 'sort_order']),
        ]

    def __str__(self) -> str:
        return f'Imagen #{self.pk} de {self.product.code}'

    def save(self, *args, **kwargs):
        needs_processing = bool(self.image) and not self.width
        is_new = self.pk is None
        if needs_processing and is_new:
            self.original_filename = self.original_filename or self._original_name()

        if self.is_primary:
            ProductImage.objects.filter(product_id=self.product_id, is_primary=True).exclude(
                pk=self.pk
            ).update(is_primary=False)

        with transaction.atomic():
            if not self.is_primary and is_new and not self._product_has_images():
                self.is_primary = True
            super().save(*args, **kwargs)
            if needs_processing:
                self._process()
                super().save(update_fields=['image', 'thumbnail', 'width', 'height', 'size_bytes'])

    def _product_has_images(self) -> bool:
        return ProductImage.objects.filter(product_id=self.product_id).exists()

    def _original_name(self) -> str:
        try:
            return self.image.name.rsplit('/', 1)[-1]
        except (AttributeError, IndexError):
            return ''

    def _process(self):
        processed = process_product_image(self.image, max_side=IMAGE_MAX_SIDE)
        self.width = processed.width
        self.height = processed.height
        self.size_bytes = processed.size_bytes
        self.image.save(f'{Path(self.image.name).stem}.webp', processed.content, save=False)

        thumbnail = process_product_thumbnail(self.image, max_side=THUMBNAIL_MAX_SIDE)
        self.thumbnail.save(f'thumb_{Path(self.image.name).stem}.webp', thumbnail.content, save=False)
