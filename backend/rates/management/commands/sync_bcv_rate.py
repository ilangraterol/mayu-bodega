"""Hourly BCV synchronisation.

Schedule it with the OS scheduler (Task Scheduler on Windows, cron on Linux)::

    python manage.py sync_bcv_rate
"""

import logging

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from rates.models import ExchangeRate
from rates.services import BcvRateNotDue, BcvSyncError, sync_bcv_rate

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Consulta la tasa oficial del BCV y la guarda en el historial.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Consulta al BCV aunque ya se haya sincronizado dentro del intervalo mínimo.',
        )

    def handle(self, *args, **options):
        current = ExchangeRate.get_current()
        if current and current.source == ExchangeRate.Source.MANUAL and current.effective_date == timezone.localdate():
            self.stdout.write(
                self.style.WARNING(
                    'La tasa vigente es MANUAL de hoy. La sincronización no sobrescribirá el historial oficial.'
                )
            )
        try:
            rate = sync_bcv_rate(force=options['force'])
        except BcvRateNotDue as error:
            self.stdout.write(self.style.WARNING(f'Sincronizacion omitida: {error}'))
            return
        except BcvSyncError as error:
            self.stderr.write(self.style.ERROR(str(error)))
            raise CommandError('No se pudo sincronizar la tasa del BCV.')
        self.stdout.write(
            self.style.SUCCESS(f'Tasa BCV guardada: {rate.rate} VES/USD (vigencia {rate.effective_date}).')
        )
