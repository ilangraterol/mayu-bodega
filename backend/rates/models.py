"""Official exchange rate history.

The rate is stored as "VES per 1 USD" and is never a float. Each row keeps both
the ``effective_date`` published by the BCV and ``fetched_at`` (when our backend
read it), so the official history is never overwritten by a manual fallback.
"""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from core.money import RATE_PLACES


class ExchangeRateQuerySet(models.QuerySet):
    def latest(self):
        return self.order_by('-effective_date', '-fetched_at', '-id')

    def current(self):
        return self.latest().first()

    def official(self):
        return self.filter(source=ExchangeRate.Source.BCV)


class ExchangeRate(models.Model):
    class Source(models.TextChoices):
        BCV = 'BCV', 'BCV (oficial)'
        MANUAL = 'MANUAL', 'Manual (fallback)'

    rate = models.DecimalField(
        max_digits=14,
        decimal_places=RATE_PLACES,
        validators=[MinValueValidator(Decimal('0.0001'))],
        help_text='Bolívares por 1 USD (VES por USD).',
    )
    effective_date = models.DateField(
        help_text='Fecha de vigencia publicada por el BCV.',
    )
    fetched_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Fecha y hora real de consulta al BCV.',
    )
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.BCV)
    is_active = models.BooleanField(default=True)
    recorded_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_exchange_rates',
    )
    notes = models.CharField(max_length=255, blank=True, default='')

    objects = ExchangeRateQuerySet.as_manager()

    class Meta:
        verbose_name = 'Tasa de cambio'
        verbose_name_plural = 'Tasas de cambio'
        ordering = ['-effective_date', '-id']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rate__gt=0),
                name='exchange_rate_gt_0',
            ),
            models.UniqueConstraint(
                fields=['source', 'effective_date'],
                name='unique_rate_per_source_and_date',
            ),
        ]
        indexes = [
            models.Index(fields=['-effective_date']),
        ]

    def __str__(self) -> str:
        return f'{self.rate} VES/USD · {self.effective_date} · {self.get_source_display()}'

    @classmethod
    def get_current(cls) -> 'ExchangeRate | None':
        return cls.objects.current()


class MissingExchangeRateError(RuntimeError):
    """No usable rate is available yet."""
