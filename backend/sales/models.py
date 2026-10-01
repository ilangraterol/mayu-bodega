"""Sales, credit debts and credit payments (abonos).

Every amount is stored in USD (``price_usd`` is the base currency of the
catalogue) plus the exchange rate that was in force at that instant, so a later
rate change never rewrites history. The only moment where the *current* rate is
re-applied to an old debt is when the customer pays in bolívares.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from core.enums import CURRENCY_CHOICES, CURRENCY_USD
from core.money import MONEY_PLACES, QUANTITY_PLACES, RATE_PLACES
from catalog.surcharge import (
    SURCHARGE_MAX_PERCENT,
    SURCHARGE_SOURCE_CHOICES,
    SURCHARGE_SOURCE_STORE,
)


class SaleType(models.TextChoices):
    PAID = 'PAID', 'Venta pagada'
    CREDIT = 'CREDIT', 'Venta fiada (crédito)'


class SaleStatus(models.TextChoices):
    COMPLETED = 'COMPLETED', 'Completada'
    ANULLED = 'ANULLED', 'Anulada'


class PaymentMethod(models.TextChoices):
    CASH_USD = 'CASH_USD', 'Efectivo USD'
    CASH_VES = 'CASH_VES', 'Efectivo VES'
    TRANSFER_USD = 'TRANSFER_USD', 'Transferencia USD'
    TRANSFER_VES = 'TRANSFER_VES', 'Transferencia VES'
    MIXED = 'MIXED', 'Mixto'
    CARD = 'CARD', 'Punto de venta'


class Sale(models.Model):
    code = models.CharField(max_length=32, unique=True, editable=False)
    sale_type = models.CharField(max_length=10, choices=SaleType.choices, default=SaleType.PAID)
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sales',
    )
    sale_date = models.DateField()
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default=CURRENCY_USD,
        help_text='Moneda en la que el cliente pagó o se fia.',
    )
    exchange_rate_applied = models.DecimalField(
        max_digits=14,
        decimal_places=RATE_PLACES,
        help_text='Tasa VES/USD vigente en el momento de la venta (inmutable).',
    )
    surcharge_percentage = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=(
            'Recargo efectivo de la venta, como porcentaje ponderado por el importe de cada '
            'línea (surge_usd / subtotal_usd * 100). Las ventas anteriores al recargo por '
            'línea guardaban aquí un único porcentaje global; el valor sigue siendo válido.'
        ),
    )
    subtotal_usd = models.DecimalField(max_digits=14, decimal_places=MONEY_PLACES, default=Decimal('0.00'))
    surcharge_usd = models.DecimalField(max_digits=14, decimal_places=MONEY_PLACES, default=Decimal('0.00'))
    total_usd = models.DecimalField(max_digits=14, decimal_places=MONEY_PLACES, default=Decimal('0.00'))
    total_ves = models.DecimalField(max_digits=16, decimal_places=MONEY_PLACES, default=Decimal('0.00'))
    paid_amount = models.DecimalField(max_digits=16, decimal_places=MONEY_PLACES, default=Decimal('0.00'))
    payment_method = models.CharField(
        max_length=16, choices=PaymentMethod.choices, default=PaymentMethod.CASH_USD
    )
    amount_due_usd = models.DecimalField(max_digits=14, decimal_places=MONEY_PLACES, default=Decimal('0.00'))
    status = models.CharField(max_length=12, choices=SaleStatus.choices, default=SaleStatus.COMPLETED)
    void_reason = models.CharField(max_length=255, blank=True, default='')
    voided_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='sales')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sale_date', '-id']
        verbose_name = 'Venta'
        verbose_name_plural = 'Ventas'
        constraints = [
            models.CheckConstraint(condition=models.Q(total_usd__gte=0), name='sale_total_gte_0'),
            models.CheckConstraint(
                condition=models.Q(amount_due_usd__gte=0), name='sale_amount_due_gte_0'
            ),
            models.CheckConstraint(
                condition=models.Q(surcharge_percentage__gte=0), name='sale_surcharge_gte_0'
            ),
        ]
        indexes = [
            models.Index(fields=['-sale_date']),
            models.Index(fields=['sale_type', '-sale_date']),
            models.Index(fields=['customer', '-sale_date']),
        ]

    def __str__(self) -> str:
        return f'{self.code} · {self.get_sale_type_display()} · {self.total_usd} USD'

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._generate_code()
        return super().save(*args, **kwargs)

    @classmethod
    def _generate_code(cls) -> str:
        last = cls.objects.order_by('-id').values_list('code', flat=True).first()
        sequence = 0
        if last and last.startswith('V'):
            try:
                sequence = int(last[1:])
            except ValueError:
                sequence = 0
        candidate = f'V{sequence + 1:06d}'
        while cls.objects.filter(code=candidate).exists():
            sequence += 1
            candidate = f'V{sequence + 1:06d}'
        return candidate

    @property
    def is_credit(self) -> bool:
        return self.sale_type == SaleType.CREDIT


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('catalog.Product', on_delete=models.PROTECT, related_name='sale_items')
    quantity = models.DecimalField(
        max_digits=12, decimal_places=QUANTITY_PLACES, validators=[MinValueValidator(Decimal('0.001'))]
    )
    unit_price_usd = models.DecimalField(max_digits=12, decimal_places=MONEY_PLACES)
    line_total_usd = models.DecimalField(max_digits=14, decimal_places=MONEY_PLACES)
    surcharge_percentage = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Recargo congelado en esta línea, ya sea del artículo, de su categoría, de la tienda o elegido en el carrito.',
    )
    surcharge_usd = models.DecimalField(
        max_digits=14,
        decimal_places=MONEY_PLACES,
        default=Decimal('0.00'),
        help_text='Importe del recargo de la línea, calculado sobre line_total_usd.',
    )
    surcharge_source = models.CharField(
        max_length=10,
        choices=SURCHARGE_SOURCE_CHOICES,
        default=SURCHARGE_SOURCE_STORE,
        help_text='Nivel del que salió el recargo aplicado en esta línea.',
    )
    unit_cost_usd = models.DecimalField(
        max_digits=12, decimal_places=MONEY_PLACES, help_text='Costo congelado al momento de la venta.'
    )

    class Meta:
        ordering = ['id']
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name='sale_item_quantity_gt_0'),
            models.CheckConstraint(
                condition=models.Q(unit_price_usd__gte=0), name='sale_item_unit_price_gte_0'
            ),
            models.CheckConstraint(
                condition=models.Q(surcharge_usd__gte=0), name='sale_item_surcharge_gte_0'
            ),
            models.CheckConstraint(
                condition=models.Q(surcharge_percentage__gte=0)
                & models.Q(surcharge_percentage__lte=SURCHARGE_MAX_PERCENT),
                name='sale_item_surcharge_between_0_and_100',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.quantity} x {self.product.code}'


class DebtStatus(models.TextChoices):
    OPEN = 'OPEN', 'Pendiente'
    PAID = 'PAID', 'Pagada'
    ANULLED = 'ANULLED', 'Anulada'


class CustomerDebt(models.Model):
    sale = models.OneToOneField(Sale, on_delete=models.PROTECT, related_name='debt')
    customer = models.ForeignKey('customers.Customer', on_delete=models.PROTECT, related_name='debts')
    original_amount_usd = models.DecimalField(max_digits=14, decimal_places=MONEY_PLACES)
    paid_amount_usd = models.DecimalField(max_digits=14, decimal_places=MONEY_PLACES, default=Decimal('0.00'))
    balance_usd = models.DecimalField(max_digits=14, decimal_places=MONEY_PLACES)
    status = models.CharField(max_length=10, choices=DebtStatus.choices, default=DebtStatus.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Deuda de cliente'
        verbose_name_plural = 'Deudas de clientes'
        constraints = [
            models.CheckConstraint(condition=models.Q(balance_usd__gte=0), name='debt_balance_gte_0'),
            models.CheckConstraint(
                condition=models.Q(paid_amount_usd__gte=0), name='debt_paid_gte_0'
            ),
        ]
        indexes = [models.Index(fields=['customer', 'status'])]

    def __str__(self) -> str:
        return f'Deuda #{self.pk} · {self.customer.name} · {self.balance_usd} USD'


class DebtPayment(models.Model):
    debt = models.ForeignKey(CustomerDebt, on_delete=models.PROTECT, related_name='payments')
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    amount = models.DecimalField(max_digits=16, decimal_places=MONEY_PLACES)
    exchange_rate_applied = models.DecimalField(
        max_digits=14,
        decimal_places=RATE_PLACES,
        help_text='Tasa vigente en la fecha del abono. Un abono en VES usa la tasa de ese día.',
    )
    amount_usd = models.DecimalField(max_digits=14, decimal_places=MONEY_PLACES)
    method = models.CharField(max_length=16, choices=PaymentMethod.choices)
    paid_at = models.DateTimeField()
    is_voided = models.BooleanField(default=False)
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=255, blank=True, default='')
    notes = models.CharField(max_length=255, blank=True, default='')
    recorded_by = models.ForeignKey(
        'auth.User', on_delete=models.PROTECT, related_name='debt_payments'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-paid_at', '-id']
        verbose_name = 'Abono de deuda'
        verbose_name_plural = 'Abonos de deudas'
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='debt_payment_amount_gt_0'),
            models.CheckConstraint(
                condition=models.Q(amount_usd__gt=0), name='debt_payment_amount_usd_gt_0'
            ),
        ]
        indexes = [models.Index(fields=['debt', '-paid_at'])]

    def __str__(self) -> str:
        return f'Abono {self.amount} {self.currency} → {self.amount_usd} USD'

    def delete(self, *args, **kwargs):
        raise ValidationError('Los abonos no se eliminan: registre una anulación auditada.')
