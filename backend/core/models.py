"""Global, single row store configuration.

A singleton (``pk=1`` enforced with a database check constraint) holding the two
global switches required by the domain:

* ``allow_zero_stock_sale``: bill products whose stock is zero.
* ``default_surcharge_percentage``: extra percentage added at the end of every
  sale (starts at 0%).
"""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class StoreConfig(models.Model):
    allow_zero_stock_sale = models.BooleanField(
        default=False,
        verbose_name='Permitir facturación con stock cero',
    )
    default_surcharge_percentage = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Recargo por defecto (%)',
    )
    store_name = models.CharField(max_length=120, default='Mayu Bodega')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='store_config_updates',
    )

    class Meta:
        verbose_name = 'Configuración de tienda'
        verbose_name_plural = 'Configuración de tienda'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(pk=1),
                name='store_config_singleton_pk_1',
            ),
        ]

    def __str__(self) -> str:
        return self.store_name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('La configuración de la tienda no se puede eliminar.')

    @classmethod
    def load(cls) -> 'StoreConfig':
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={'allow_zero_stock_sale': False, 'default_surcharge_percentage': Decimal('0.00')},
        )
        return obj
