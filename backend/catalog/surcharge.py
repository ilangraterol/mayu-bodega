"""Surcharge (recargo) rules shared by the catalogue and the point of sale.

The percentage that applies to a cart line is resolved in a single place, in
this order:

1. the value the cashier chose for that line at the till (it freezes into the
   sale and becomes the article's new value);
2. the article's own ``surcharge_percentage``;
3. its category's ``surcharge_percentage``;
4. the store-wide ``StoreConfig.default_surcharge_percentage``.

Levels 2 and 3 are nullable on purpose: ``None`` means "inherit", so a category
can exist without defining a percentage and the store default still applies.
Only level 1 can be missing from a request, in which case the resolution falls
through to the catalogue.

The surcharge is applied **per line**: a 30% article and a 10% article sold
together do not contaminate each other, so totals are summed line by line and
never from a single percentage over the whole subtotal.
"""

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

SURCHARGE_MIN_PERCENT = Decimal('0.00')
SURCHARGE_MAX_PERCENT = Decimal('100.00')
_HUNDRED = Decimal('100')
_PERCENT_PLACES = Decimal('0.01')

SURCHARGE_SOURCE_MANUAL = 'MANUAL'
SURCHARGE_SOURCE_PRODUCT = 'PRODUCT'
SURCHARGE_SOURCE_CATEGORY = 'CATEGORY'
SURCHARGE_SOURCE_STORE = 'STORE'

SURCHARGE_SOURCE_CHOICES = [
    (SURCHARGE_SOURCE_MANUAL, 'Elegido en el carrito'),
    (SURCHARGE_SOURCE_PRODUCT, 'Artículo'),
    (SURCHARGE_SOURCE_CATEGORY, 'Categoría'),
    (SURCHARGE_SOURCE_STORE, 'Tienda'),
]

#: Quick-pick percentages offered by the till. They are shortcuts only: any
#: value in [0, 100] is accepted, both here and in the catalogue.
SURCHARGE_PRESETS = [Decimal('3.00'), Decimal('5.00'), Decimal('10.00'), Decimal('15.00'), Decimal('30.00')]

SURCHARGE_PRESET_VALUES = ['3', '5', '10', '15', '30']


def coerce_surcharge(value, *, allow_none: bool = False, field: str = 'surcharge_percentage'):
    """Return ``value`` as a ``Decimal`` percentage in [0, 100].

    ``None`` is accepted only when ``allow_none`` is set, which is how the
    catalogue expresses "this level does not define a surcharge".
    """
    if value is None or value == '':
        if allow_none:
            return None
        raise ValidationError({field: 'Indique el porcentaje de recargo.'})

    try:
        percentage = Decimal(str(value))
    except (ArithmeticError, InvalidOperation, TypeError, ValueError):
        raise ValidationError({field: 'El recargo debe ser un número.'})

    if not percentage.is_finite():
        raise ValidationError({field: 'El recargo debe ser un número.'})
    if percentage < SURCHARGE_MIN_PERCENT or percentage > SURCHARGE_MAX_PERCENT:
        raise ValidationError({field: 'El recargo debe estar entre 0 y 100%.'})

    return percentage.quantize(_PERCENT_PLACES)


def resolve_surcharge(product, store_default) -> tuple[Decimal, str]:
    """Resolve the catalogue surcharge of ``product``: article > category > store.

    Returns the percentage together with the level that provided it, so the API
    can tell the cashier why a line starts at that number.
    """
    store_default = coerce_surcharge(store_default, allow_none=True)
    default = store_default if store_default is not None else SURCHARGE_MIN_PERCENT

    if product.surcharge_percentage is not None:
        return coerce_surcharge(product.surcharge_percentage), SURCHARGE_SOURCE_PRODUCT

    category = getattr(product, 'category', None)
    if category is not None and category.surcharge_percentage is not None:
        return coerce_surcharge(category.surcharge_percentage), SURCHARGE_SOURCE_CATEGORY

    return default, SURCHARGE_SOURCE_STORE


def surcharge_label(source: str) -> str:
    return dict(SURCHARGE_SOURCE_CHOICES).get(source, source)


def apply_percentage(amount: Decimal, percentage: Decimal) -> Decimal:
    """The surcharge amount for ``amount`` at ``percentage``, kept quantized."""
    return (amount * (percentage / _HUNDRED)).quantize(_PERCENT_PLACES)
