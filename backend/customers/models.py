"""Customers audited for credit (fiado) and payment history."""

from django.db import models


class Customer(models.Model):
    document_id = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name='Cédula / documento',
        help_text='Identificación del cliente. Déjelo vacío para clientes sin documento.',
    )
    name = models.CharField(max_length=180)
    phone = models.CharField(max_length=32, blank=True, default='')
    address = models.CharField(max_length=255, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self) -> str:
        return f'{self.name} ({self.document_id})' if self.document_id else self.name

    @property
    def display_name(self) -> str:
        return self.name
