"""Domain enumerations shared by models, serializers and services."""

CURRENCY_USD = 'USD'
CURRENCY_VES = 'VES'

CURRENCY_CHOICES = [
    (CURRENCY_USD, 'Dólares (USD)'),
    (CURRENCY_VES, 'Bolívares (VES)'),
]

SUPPORTED_CURRENCIES = [code for code, _ in CURRENCY_CHOICES]
