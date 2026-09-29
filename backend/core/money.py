"""Money helpers.

Money is never stored as float/double. Amounts are ``Decimal`` with 2 decimal
places and exchange rates with 4 decimal places (both enforced by the database
column definitions).

Rounding policy: half-up (``ROUND_HALF_UP``), applied when persisting amounts and
when converting VES into USD. This is an assumption to confirm with the user
before going to production.
"""

from decimal import ROUND_HALF_UP, Decimal

MONEY_PLACES = 2
RATE_PLACES = 4
QUANTITY_PLACES = 3

MONEY_QUANTUM = Decimal('0.01')
RATE_QUANTUM = Decimal('0.0001')
QUANTITY_QUANTUM = Decimal('0.001')


def as_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def quantize_money(value) -> Decimal:
    return as_decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def quantize_rate(value) -> Decimal:
    return as_decimal(value).quantize(RATE_QUANTUM, rounding=ROUND_HALF_UP)


def quantize_quantity(value) -> Decimal:
    return as_decimal(value).quantize(QUANTITY_QUANTUM, rounding=ROUND_HALF_UP)


def usd_to_ves(amount_usd, rate_ves_per_usd) -> Decimal:
    return quantize_money(as_decimal(amount_usd) * as_decimal(rate_ves_per_usd))


def ves_to_usd(amount_ves, rate_ves_per_usd) -> Decimal:
    rate = as_decimal(rate_ves_per_usd)
    if rate <= 0:
        raise ValueError('La tasa de cambio debe ser mayor que cero.')
    return quantize_money(as_decimal(amount_ves) / rate)
