"""Inventory domain services.

Every stock change goes through :func:`record_movement`, which runs inside a
transaction, locks the product row and refuses to produce a negative balance.
Corrections are new opposing movements, never edits of past rows.
"""

import logging
from datetime import date, datetime, time
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from catalog.models import Product
from core.enums import CURRENCY_USD, CURRENCY_VES
from core.money import quantize_money, quantize_quantity, ves_to_usd
from inventory.models import (
    ExitNote,
    ExitNoteItem,
    GoodsEntry,
    GoodsEntryItem,
    StockMovement,
)
from rates.services import get_current_rate

logger = logging.getLogger(__name__)

ZERO = Decimal('0.000')


class InsufficientStockError(ValidationError):
    pass


def moment_on(day: date) -> datetime:
    """Timezone aware timestamp for a given business day (end of day local time)."""
    local = timezone.get_current_timezone()
    naive = datetime.combine(day, time(23, 59, 59))
    return timezone.make_aware(naive, local)


@transaction.atomic
def record_movement(
    *,
    product_id: int,
    movement_type: str,
    origin: str,
    origin_id: int | None,
    quantity,
    user=None,
    unit_cost_usd=None,
    unit_price_usd=None,
    notes: str = '',
    reversal_of: StockMovement | None = None,
    occurred_at=None,
    allow_shortage: bool = False,
) -> StockMovement:
    """Append one movement and refresh ``Product.stock`` / ``pending_units``.

    The ledger invariant is ``sum(signed movements) == stock - pending_units``:

    * an **IN** clears any outstanding ``pending_units`` first, and only the
      remainder lands in physical stock;
    * an **OUT** deducts physical stock; if it is not enough and the store
      allows billing with zero stock, the deficit becomes ``pending_units``
      instead of a negative balance.
    """
    product = Product.objects.select_for_update().get(pk=product_id)
    quantity = quantize_quantity(quantity)
    if quantity <= 0:
        raise ValidationError('La cantidad debe ser mayor que cero.')

    stock_before = product.stock or ZERO
    pending_before = product.pending_units or ZERO
    is_incoming = movement_type == StockMovement.MovementType.IN

    if is_incoming:
        cleared = min(quantity, pending_before)
        pending_after = quantize_quantity(pending_before - cleared)
        balance_after = quantize_quantity(stock_before + (quantity - cleared))
    else:
        balance_after = quantize_quantity(stock_before - quantity)
        pending_after = pending_before
        if balance_after < 0:
            if not allow_shortage:
                raise InsufficientStockError(
                    f'Stock insuficiente para {product.code} ({product.name}). '
                    f'Disponible: {stock_before}, solicitado: {quantity}.'
                )
            pending_after = quantize_quantity(pending_before + (quantity - stock_before))
            balance_after = ZERO

    movement = StockMovement.objects.create(
        product=product,
        movement_type=movement_type,
        origin=origin,
        origin_id=origin_id,
        quantity=quantity,
        unit_cost_usd=quantize_money(unit_cost_usd) if unit_cost_usd is not None else None,
        unit_price_usd=quantize_money(unit_price_usd) if unit_price_usd is not None else None,
        balance_after=balance_after,
        pending_after=pending_after,
        occurred_at=occurred_at or timezone.now(),
        notes=notes[:255],
        reversal_of=reversal_of,
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )

    Product.objects.filter(pk=product.pk).update(stock=balance_after, pending_units=pending_after)
    logger.info(
        'Movimiento %s %s %s (saldo %s, pendiente %s).',
        movement.movement_type,
        movement.quantity,
        product.code,
        balance_after,
        pending_after,
    )
    return movement


@transaction.atomic
def register_entry(
    *,
    user,
    entry_date: date,
    items: list[dict],
    supplier_name: str = '',
    currency: str = CURRENCY_USD,
    notes: str = '',
    rate_applied=None,
) -> GoodsEntry:
    """Receive merchandise.

    ``items`` -> ``[{'product_id': int, 'quantity': str, 'unit_cost': str}]``.
    When ``currency`` is VES the current BCV rate is captured once and applied
    to every line, so the entry keeps a single auditable rate.
    """
    if not items:
        raise ValidationError('La entrada debe tener al menos un producto.')

    if currency == CURRENCY_VES and rate_applied is None:
        rate_applied = get_current_rate().rate

    entry = GoodsEntry.objects.create(
        supplier_name=(supplier_name or '').strip()[:150],
        entry_date=entry_date,
        currency=currency,
        rate_applied=rate_applied if currency == CURRENCY_VES else None,
        notes=notes or '',
        created_by=user,
    )

    occurred_at = moment_on(entry_date)
    total_usd = ZERO

    for raw in items:
        product_id = raw.get('product_id') or raw.get('product')
        if product_id is None:
            raise ValidationError('Cada línea de la entrada debe indicar el producto.')

        quantity = quantize_quantity(raw['quantity'])
        unit_cost = quantize_money(raw['unit_cost'])
        if quantity <= 0 or unit_cost <= 0:
            raise ValidationError('Cantidad y costo de compra deben ser mayores que cero.')

        if not Product.objects.filter(pk=product_id).exists():
            raise ValidationError(f'El artículo con id {product_id} no existe en el catálogo.')

        unit_cost_usd = ves_to_usd(unit_cost, rate_applied) if currency == CURRENCY_VES else unit_cost
        line_total_usd = quantize_money(quantity * unit_cost_usd)
        total_usd = quantize_money(total_usd + line_total_usd)

        GoodsEntryItem.objects.create(
            entry=entry,
            product_id=product_id,
            quantity=quantity,
            unit_cost=unit_cost,
            currency=currency,
            rate_applied=rate_applied if currency == CURRENCY_VES else None,
            unit_cost_usd=unit_cost_usd,
            line_total_usd=line_total_usd,
        )

        record_movement(
            product_id=product_id,
            movement_type=StockMovement.MovementType.IN,
            origin=StockMovement.Origin.ENTRADA,
            origin_id=entry.id,
            quantity=quantity,
            user=user,
            unit_cost_usd=unit_cost_usd,
            occurred_at=occurred_at,
        )

        Product.objects.filter(pk=product_id).update(cost_usd=unit_cost_usd)

    GoodsEntry.objects.filter(pk=entry.pk).update(total_usd=total_usd)
    entry.total_usd = total_usd
    return entry


@transaction.atomic
def register_exit_note(
    *,
    user,
    exit_date: date,
    reason: str,
    description: str,
    items: list[dict],
) -> ExitNote:
    """Issue an explicit, justified stock deduction note."""
    if not items:
        raise ValidationError('La nota de salida debe tener al menos un producto.')
    if not (description or '').strip():
        raise ValidationError('Describa el motivo de la salida.')

    note = ExitNote.objects.create(
        reason=reason,
        description=description.strip(),
        exit_date=exit_date,
        created_by=user,
    )

    occurred_at = moment_on(exit_date)
    total_units = ZERO

    for raw in items:
        product_id = raw.get('product_id') or raw.get('product')
        if product_id is None:
            raise ValidationError('Cada línea de la nota debe indicar el producto.')

        quantity = quantize_quantity(raw['quantity'])
        if quantity <= 0:
            raise ValidationError('La cantidad debe ser mayor que cero.')

        product = Product.objects.filter(pk=product_id).first()
        if product is None:
            raise ValidationError(f'El artículo con id {product_id} no existe en el catálogo.')
        unit_cost_usd = product.cost_usd

        ExitNoteItem.objects.create(
            note=note,
            product=product,
            quantity=quantity,
            unit_cost_usd=unit_cost_usd,
        )

        record_movement(
            product_id=product_id,
            movement_type=StockMovement.MovementType.OUT,
            origin=StockMovement.Origin.NOTA_SALIDA,
            origin_id=note.id,
            quantity=quantity,
            user=user,
            unit_cost_usd=unit_cost_usd,
            notes=f'{note.get_reason_display()} · {note.code}',
            occurred_at=occurred_at,
        )
        total_units = quantize_quantity(total_units + quantity)

    ExitNote.objects.filter(pk=note.pk).update(total_units=total_units)
    note.total_units = total_units
    return note


@transaction.atomic
def cancel_entry(*, user, entry: GoodsEntry, reason: str) -> GoodsEntry:
    """Cancel an entry by appending the opposing movements (history is kept)."""
    if entry.is_cancelled:
        raise ValidationError('La entrada ya está anulada.')

    for item in entry.items.all():
        original = StockMovement.objects.filter(
            origin=StockMovement.Origin.ENTRADA, origin_id=entry.id, product_id=item.product_id
        ).first()
        record_movement(
            product_id=item.product_id,
            movement_type=StockMovement.MovementType.OUT,
            origin=StockMovement.Origin.ANULACION,
            origin_id=entry.id,
            quantity=item.quantity,
            user=user,
            unit_cost_usd=item.unit_cost_usd,
            notes=f'Anulación de {entry.code}. {reason}'.strip(),
            reversal_of=original,
        )

    entry.is_cancelled = True
    entry.cancelled_at = timezone.now()
    entry.save(update_fields=['is_cancelled', 'cancelled_at'])
    return entry


@transaction.atomic
def cancel_exit_note(*, user, note: ExitNote, reason: str) -> ExitNote:
    """Cancel an exit note by appending the opposing movements."""
    if note.is_cancelled:
        raise ValidationError('La nota de salida ya está anulada.')

    for item in note.items.all():
        original = StockMovement.objects.filter(
            origin=StockMovement.Origin.NOTA_SALIDA, origin_id=note.id, product_id=item.product_id
        ).first()
        record_movement(
            product_id=item.product_id,
            movement_type=StockMovement.MovementType.IN,
            origin=StockMovement.Origin.ANULACION,
            origin_id=note.id,
            quantity=item.quantity,
            user=user,
            unit_cost_usd=item.unit_cost_usd,
            notes=f'Anulación de {note.code}. {reason}'.strip(),
            reversal_of=original,
        )

    note.is_cancelled = True
    note.cancelled_at = timezone.now()
    note.save(update_fields=['is_cancelled', 'cancelled_at'])
    return note


def stock_on_hand(product: Product) -> Decimal:
    return product.stock or ZERO
