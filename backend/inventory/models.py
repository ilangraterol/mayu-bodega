"""Stock movements, goods entries and exit notes.

``StockMovement`` is an append only ledger: movements are never edited or
deleted. Corrections are recorded as new opposing movements so the history stays
immutable.

``Product.stock`` and ``Product.pending_units`` are denormalised balances
refreshed inside the same transaction as the movement. ``stock`` is the physical
on-hand quantity and never goes negative; ``pending_units`` holds units that were
sold while the store allowed billing with zero stock. The invariant preserved by
every movement is::

    sum(signed movements) == stock - pending_units
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from core.enums import CURRENCY_CHOICES, CURRENCY_USD
from core.money import MONEY_PLACES, QUANTITY_PLACES, RATE_PLACES


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        IN = 'IN', 'Entrada'
        OUT = 'OUT', 'Salida'

    class Origin(models.TextChoices):
        ENTRADA = 'ENTRADA', 'Entrada de mercancía'
        VENTA = 'VENTA', 'Venta'
        NOTA_SALIDA = 'NOTA_SALIDA', 'Nota de salida'
        ANULACION = 'ANULACION', 'Anulación'

    product = models.ForeignKey('catalog.Product', on_delete=models.PROTECT, related_name='movements')
    movement_type = models.CharField(max_length=3, choices=MovementType.choices)
    origin = models.CharField(max_length=20, choices=Origin.choices)
    origin_id = models.IntegerField(null=True, blank=True, help_text='PK del documento origen.')
    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=QUANTITY_PLACES,
        validators=[MinValueValidator(Decimal('0.001'))],
    )
    unit_cost_usd = models.DecimalField(
        max_digits=12,
        decimal_places=MONEY_PLACES,
        null=True,
        blank=True,
    )
    balance_after = models.DecimalField(max_digits=12, decimal_places=QUANTITY_PLACES)
    pending_after = models.DecimalField(
        max_digits=12,
        decimal_places=QUANTITY_PLACES,
        default=Decimal('0.000'),
        help_text='Unidades pendientes de reposición tras este movimiento.',
    )
    unit_price_usd = models.DecimalField(
        max_digits=12,
        decimal_places=MONEY_PLACES,
        null=True,
        blank=True,
        help_text='Precio de venta unitario en el momento del movimiento (sólo ventas).',
    )
    occurred_at = models.DateTimeField()
    notes = models.CharField(max_length=255, blank=True, default='')
    reversal_of = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='reversals',
    )
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_movements'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-occurred_at', '-id']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name='stock_movement_quantity_gt_0',
            ),
            models.CheckConstraint(
                condition=models.Q(balance_after__gte=0),
                name='stock_movement_balance_gte_0',
            ),
            models.CheckConstraint(
                condition=models.Q(pending_after__gte=0),
                name='stock_movement_pending_gte_0',
            ),
        ]
        indexes = [
            models.Index(fields=['product', '-occurred_at']),
            models.Index(fields=['origin', 'origin_id']),
        ]

    def __str__(self) -> str:
        sign = '+' if self.movement_type == self.MovementType.IN else '-'
        return f'{sign}{self.quantity} {self.product.code} ({self.get_origin_display()})'

    @property
    def signed_quantity(self) -> Decimal:
        if self.movement_type == self.MovementType.IN:
            return self.quantity
        return -self.quantity

    @property
    def net_position_after(self) -> Decimal:
        """``stock - pending_units`` right after this movement."""
        return self.balance_after - self.pending_after

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError('Los movimientos de inventario son inmutables: registre un movimiento nuevo.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Los movimientos de inventario no se pueden eliminar.')


class GoodsEntry(models.Model):
    code = models.CharField(max_length=32, unique=True, editable=False)
    supplier_name = models.CharField(max_length=150, blank=True, default='')
    entry_date = models.DateField()
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default=CURRENCY_USD)
    rate_applied = models.DecimalField(
        max_digits=14,
        decimal_places=RATE_PLACES,
        null=True,
        blank=True,
        help_text='Tasa VES/USD aplicada cuando el costo se registró en bolívares.',
    )
    total_usd = models.DecimalField(max_digits=14, decimal_places=MONEY_PLACES, default=Decimal('0.00'))
    notes = models.TextField(blank=True, default='')
    is_cancelled = models.BooleanField(default=False)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        'auth.User', on_delete=models.PROTECT, related_name='goods_entries'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-entry_date', '-id']
        verbose_name = 'Entrada de mercancía'
        verbose_name_plural = 'Entradas de mercancía'
        indexes = [models.Index(fields=['-entry_date'])]

    def __str__(self) -> str:
        return f'{self.code} · {self.entry_date}'

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._generate_code()
        return super().save(*args, **kwargs)

    @classmethod
    def _generate_code(cls) -> str:
        last = cls.objects.order_by('-id').values_list('code', flat=True).first()
        sequence = 0
        if last and last.startswith('E'):
            try:
                sequence = int(last[1:])
            except ValueError:
                sequence = 0
        candidate = f'E{sequence + 1:06d}'
        while cls.objects.filter(code=candidate).exists():
            sequence += 1
            candidate = f'E{sequence + 1:06d}'
        return candidate


class GoodsEntryItem(models.Model):
    entry = models.ForeignKey(GoodsEntry, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('catalog.Product', on_delete=models.PROTECT, related_name='entry_items')
    quantity = models.DecimalField(
        max_digits=12, decimal_places=QUANTITY_PLACES, validators=[MinValueValidator(Decimal('0.001'))]
    )
    unit_cost = models.DecimalField(max_digits=12, decimal_places=MONEY_PLACES)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default=CURRENCY_USD)
    rate_applied = models.DecimalField(
        max_digits=14, decimal_places=RATE_PLACES, null=True, blank=True
    )
    unit_cost_usd = models.DecimalField(max_digits=12, decimal_places=MONEY_PLACES)
    line_total_usd = models.DecimalField(max_digits=14, decimal_places=MONEY_PLACES)

    class Meta:
        ordering = ['id']
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name='entry_item_quantity_gt_0'),
            models.CheckConstraint(condition=models.Q(unit_cost__gt=0), name='entry_item_unit_cost_gt_0'),
        ]

    def __str__(self) -> str:
        return f'{self.quantity} x {self.product.code}'


class ExitNoteReason(models.TextChoices):
    MERMA = 'MERMA', 'Merma'
    CONSUMO_INTERNO = 'CONSUMO_INTERNO', 'Consumo interno'
    PERDIDA = 'PERDIDA', 'Pérdida'
    DEVOLUCION = 'DEVOLUCION', 'Devolución de mercancía'
    DANO = 'DANO', 'Producto dañado'
    VENCIMIENTO = 'VENCIMIENTO', 'Vencimiento'
    OTRO = 'OTRO', 'Otro'


class ExitNote(models.Model):
    code = models.CharField(max_length=32, unique=True, editable=False)
    reason = models.CharField(max_length=20, choices=ExitNoteReason.choices)
    description = models.TextField()
    exit_date = models.DateField()
    total_units = models.DecimalField(max_digits=14, decimal_places=QUANTITY_PLACES, default=Decimal('0.000'))
    is_cancelled = models.BooleanField(default=False)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='exit_notes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-exit_date', '-id']
        verbose_name = 'Nota de salida'
        verbose_name_plural = 'Notas de salida'
        indexes = [models.Index(fields=['-exit_date'])]

    def __str__(self) -> str:
        return f'{self.code} · {self.get_reason_display()} · {self.exit_date}'

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._generate_code()
        return super().save(*args, **kwargs)

    @classmethod
    def _generate_code(cls) -> str:
        last = cls.objects.order_by('-id').values_list('code', flat=True).first()
        sequence = 0
        if last and last.startswith('S'):
            try:
                sequence = int(last[1:])
            except ValueError:
                sequence = 0
        candidate = f'S{sequence + 1:06d}'
        while cls.objects.filter(code=candidate).exists():
            sequence += 1
            candidate = f'S{sequence + 1:06d}'
        return candidate


class ExitNoteItem(models.Model):
    note = models.ForeignKey(ExitNote, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('catalog.Product', on_delete=models.PROTECT, related_name='exit_note_items')
    quantity = models.DecimalField(
        max_digits=12, decimal_places=QUANTITY_PLACES, validators=[MinValueValidator(Decimal('0.001'))]
    )
    unit_cost_usd = models.DecimalField(
        max_digits=12, decimal_places=MONEY_PLACES, null=True, blank=True
    )

    class Meta:
        ordering = ['id']
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name='exit_item_quantity_gt_0'),
        ]

    def __str__(self) -> str:
        return f'{self.quantity} x {self.product.code}'
