"""Sales and credit (fiado) domain services.

Rules implemented here (never in views or serializers):

* a sale freezes the BCV rate, the surcharge percentage and the unit prices;
* stock is deducted atomically, and blocked when it is insufficient unless the
  store allows billing with zero stock;
* a credit sale requires a customer and opens a debt denominated in USD;
* a payment in bolívares re-prices the pending USD balance with *today's* rate;
* corrections (voids) append compensating movements, they never delete rows.
"""

import logging
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.enums import CURRENCY_USD, CURRENCY_VES
from core.money import quantize_money, quantize_quantity, usd_to_ves, ves_to_usd
from core.models import StoreConfig
from customers.models import Customer
from inventory.models import StockMovement
from inventory.services import record_movement
from rates.services import get_current_rate, get_rate_for_date
from sales.models import (
    CustomerDebt,
    DebtPayment,
    DebtStatus,
    PaymentMethod,
    Sale,
    SaleItem,
    SaleStatus,
    SaleType,
)

logger = logging.getLogger(__name__)

ZERO = Decimal('0.00')


class OutOfStockError(ValidationError):
    pass


def compute_totals(lines: list[dict], surcharge_percentage: Decimal) -> dict:
    """``lines`` -> ``[{'product_id', 'quantity', 'unit_price_usd'}]``."""
    subtotal = ZERO
    for line in lines:
        line_total = quantize_quantity(line['quantity']) * quantize_money(line['unit_price_usd'])
        subtotal = quantize_money(subtotal + line_total)
    surcharge = quantize_money(subtotal * (quantize_money(surcharge_percentage) / Decimal('100')))
    return {
        'subtotal_usd': subtotal,
        'surcharge_usd': surcharge,
        'total_usd': quantize_money(subtotal + surcharge),
    }


def _resolve_lines(items: list[dict]) -> list[dict]:
    """Validate every line and fall back to the catalogue price when not given."""
    from catalog.models import Product

    normalized = []
    for raw in items:
        product_id = raw.get('product_id') or raw.get('product')
        if product_id is None:
            raise ValidationError('Cada línea de la venta debe indicar el producto.')

        quantity = quantize_quantity(raw['quantity'])
        if quantity <= 0:
            raise ValidationError('La cantidad debe ser mayor que cero.')

        product = Product.objects.filter(pk=product_id).first()
        if product is None:
            raise ValidationError('Artículo no encontrado.')
        if not product.is_active:
            raise ValidationError(f'El artículo {product.name} está inactivo.')

        unit_price = raw.get('unit_price_usd')
        unit_price = product.price_usd if unit_price is None else quantize_money(unit_price)
        if unit_price < 0:
            raise ValidationError('El precio no puede ser negativo.')

        normalized.append(
            {
                'product_id': product.pk,
                'quantity': quantity,
                'unit_price_usd': unit_price,
                'product': product,
            }
        )
    return normalized


@transaction.atomic
def create_sale(
    *,
    user,
    items: list[dict],
    sale_type: str,
    sale_date: date | None = None,
    customer: Customer | None = None,
    currency: str = CURRENCY_USD,
    paid_amount=None,
    payment_method: str = PaymentMethod.CASH_USD,
    notes: str = '',
) -> Sale:
    if not items:
        raise ValidationError('La venta debe tener al menos un producto.')

    if sale_type == SaleType.CREDIT:
        if customer is None:
            raise ValidationError('Una venta fiada requiere un cliente.')
        if not customer.is_active:
            raise ValidationError(f'El cliente {customer.name} está inactivo.')
    else:
        customer = None

    config = StoreConfig.load()
    rate = get_current_rate().rate
    surcharge_percentage = quantize_money(config.default_surcharge_percentage)
    sale_date = sale_date or timezone.localdate()

    normalized = _resolve_lines(items)
    totals = compute_totals(normalized, surcharge_percentage)

    sale = Sale.objects.create(
        sale_type=sale_type,
        customer=customer,
        sale_date=sale_date,
        currency=currency,
        exchange_rate_applied=rate,
        surcharge_percentage=surcharge_percentage,
        subtotal_usd=totals['subtotal_usd'],
        surcharge_usd=totals['surcharge_usd'],
        total_usd=totals['total_usd'],
        total_ves=usd_to_ves(totals['total_usd'], rate),
        payment_method=payment_method,
        notes=notes or '',
        created_by=user,
    )

    for line in normalized:
        product = _lock_product(line['product_id'])
        line_total = quantize_money(line['quantity'] * line['unit_price_usd'])

        if not config.allow_zero_stock_sale and (product.stock or ZERO) < line['quantity']:
            raise OutOfStockError(
                f'Stock insuficiente para {product.code} ({product.name}). '
                f'Disponible: {product.stock}, solicitado: {line["quantity"]}.'
            )

        SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=line['quantity'],
            unit_price_usd=line['unit_price_usd'],
            line_total_usd=line_total,
            unit_cost_usd=product.cost_usd,
        )

        record_movement(
            product_id=product.pk,
            movement_type=StockMovement.MovementType.OUT,
            origin=StockMovement.Origin.VENTA,
            origin_id=sale.id,
            quantity=line['quantity'],
            user=user,
            unit_cost_usd=product.cost_usd,
            unit_price_usd=line['unit_price_usd'],
            notes=sale.code,
            allow_shortage=config.allow_zero_stock_sale,
        )

    _settle_sale(sale=sale, paid_amount=paid_amount, currency=currency)
    return sale


def _lock_product(product_id):
    from catalog.models import Product

    return Product.objects.select_for_update().get(pk=product_id)


def _settle_sale(*, sale: Sale, paid_amount, currency: str) -> None:
    if sale.is_credit:
        sale.paid_amount = ZERO
        sale.amount_due_usd = sale.total_usd
        sale.save(update_fields=['paid_amount', 'amount_due_usd'])
        CustomerDebt.objects.create(
            sale=sale,
            customer=sale.customer,
            original_amount_usd=sale.total_usd,
            paid_amount_usd=ZERO,
            balance_usd=sale.total_usd,
            status=DebtStatus.OPEN,
        )
        return

    if paid_amount is None:
        raise ValidationError('Indique el monto pagado en una venta pagada.')

    paid = quantize_money(paid_amount)
    paid_usd = ves_to_usd(paid, sale.exchange_rate_applied) if currency == CURRENCY_VES else paid

    if paid_usd < sale.total_usd:
        raise ValidationError(
            f'El pago es menor al total de la venta ({sale.total_usd} USD). '
            'Registre la diferencia como venta fiada.'
        )

    sale.paid_amount = paid
    sale.amount_due_usd = quantize_money(paid_usd - sale.total_usd)
    sale.save(update_fields=['paid_amount', 'amount_due_usd'])


@transaction.atomic
def register_payment(
    *,
    user,
    debt: CustomerDebt,
    amount,
    currency: str,
    method: str,
    paid_at=None,
    notes: str = '',
) -> DebtPayment:
    """Register a credit payment (abono).

    The pending USD balance is re-priced with the rate in force *at the moment of
    the payment*: that is the only moment a current rate is applied to an old
    debt. When the payment is backdated the rate published for that date is used,
    so the stored ``exchange_rate_applied`` always matches ``paid_at``.
    """
    debt = CustomerDebt.objects.select_for_update().get(pk=debt.pk)
    if debt.status == DebtStatus.PAID:
        raise ValidationError('La deuda ya está pagada.')
    if debt.status == DebtStatus.ANULLED:
        raise ValidationError('La deuda fue anulada.')

    amount = quantize_money(amount)
    if amount <= 0:
        raise ValidationError('El monto del abono debe ser mayor que cero.')

    paid_at = paid_at or timezone.now()
    if paid_at > timezone.now():
        raise ValidationError('El abono no puede tener una fecha futura.')
    rate = get_rate_for_date(timezone.localtime(paid_at).date()).rate
    amount_usd = ves_to_usd(amount, rate) if currency == CURRENCY_VES else amount

    if amount_usd > debt.balance_usd:
        raise ValidationError(
            f'El abono ({amount_usd} USD) supera el saldo pendiente ({debt.balance_usd} USD). '
            f'El máximo a abonar hoy es {usd_to_ves(debt.balance_usd, rate)} VES '
            f'o {debt.balance_usd} USD.'
        )

    payment = DebtPayment.objects.create(
        debt=debt,
        currency=currency,
        amount=amount,
        exchange_rate_applied=rate,
        amount_usd=amount_usd,
        method=method,
        paid_at=paid_at,
        notes=notes[:255],
        recorded_by=user,
    )

    debt.paid_amount_usd = quantize_money(debt.paid_amount_usd + amount_usd)
    debt.balance_usd = quantize_money(debt.balance_usd - amount_usd)
    if debt.balance_usd <= ZERO:
        debt.balance_usd = ZERO
        debt.status = DebtStatus.PAID
    debt.save(update_fields=['paid_amount_usd', 'balance_usd', 'status', 'updated_at'])

    logger.info('Abono %s USD sobre deuda #%s.', amount_usd, debt.pk)
    return payment


@transaction.atomic
def void_payment(*, user, payment: DebtPayment, reason: str) -> DebtPayment:
    """Void a payment: the row is kept and the balance is restored."""
    if payment.is_voided:
        raise ValidationError('El abono ya está anulado.')

    debt = CustomerDebt.objects.select_for_update().get(pk=payment.debt_id)
    if debt.status == DebtStatus.ANULLED:
        raise ValidationError('La deuda fue anulada.')

    debt.paid_amount_usd = quantize_money(debt.paid_amount_usd - payment.amount_usd)
    debt.balance_usd = quantize_money(debt.balance_usd + payment.amount_usd)
    debt.status = DebtStatus.OPEN if debt.balance_usd > ZERO else DebtStatus.PAID
    debt.save(update_fields=['paid_amount_usd', 'balance_usd', 'status', 'updated_at'])

    payment.is_voided = True
    payment.voided_at = timezone.now()
    payment.void_reason = reason[:255]
    payment.save(update_fields=['is_voided', 'voided_at', 'void_reason'])
    logger.info('Abono #%s anulado por %s.', payment.pk, user)
    return payment


@transaction.atomic
def void_sale(*, user, sale: Sale, reason: str) -> Sale:
    """Void a sale: stock comes back and the debt is closed, nothing is deleted."""
    sale = Sale.objects.select_for_update().get(pk=sale.pk)
    if sale.status == SaleStatus.ANULLED:
        raise ValidationError('La venta ya está anulada.')
    if not (reason or '').strip():
        raise ValidationError('Indique el motivo de la anulación.')

    debt = getattr(sale, 'debt', None)
    if debt and debt.status == DebtStatus.OPEN:
        raise ValidationError(
            'La venta fiada tiene saldo pendiente. Anule los abonos o Cobré antes de anular la venta.'
        )

    for item in sale.items.all():
        original = StockMovement.objects.filter(
            origin=StockMovement.Origin.VENTA, origin_id=sale.id, product_id=item.product_id
        ).first()
        record_movement(
            product_id=item.product_id,
            movement_type=StockMovement.MovementType.IN,
            origin=StockMovement.Origin.ANULACION,
            origin_id=sale.id,
            quantity=item.quantity,
            user=user,
            unit_cost_usd=item.unit_cost_usd,
            unit_price_usd=item.unit_price_usd,
            notes=f'Anulación de {sale.code}. {reason}'.strip(),
            reversal_of=original,
        )

    if debt:
        debt.status = DebtStatus.ANULLED
        debt.balance_usd = ZERO
        debt.save(update_fields=['status', 'balance_usd', 'updated_at'])

    sale.status = SaleStatus.ANULLED
    sale.void_reason = reason[:255]
    sale.voided_at = timezone.now()
    sale.save(update_fields=['status', 'void_reason', 'voided_at'])
    logger.info('Venta %s anulada por %s.', sale.code, user)
    return sale
