"""Carga de existencia inicial para productos que hoy están en cero.

Los movimientos se registran con ``record_movement`` y no con ``register_entry``
a propósito: una ``GoodsEntryItem`` exige ``unit_cost > 0`` y esa entrada además
escribe ese valor en ``Product.cost_usd``. Como el catálogo de Cost Azul todavía
no tiene costo de compra real, esta carga deja el costo intacto en cero para no
inventar márgenes en los reportes.

El saldo nunca se escribe directo a ``Product.stock``: pasa por el ledger
inmutable, de modo que la invariante ``sum(movimientos) == stock - pending_units``
se mantiene y cada unidad queda auditable.

    python manage.py seed_stock --dry-run
    python manage.py seed_stock --min 1 --max 10
    python manage.py seed_stock --include-filled   # suma sobre lo que ya hay
"""

import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from catalog.models import Product
from inventory.models import StockMovement
from inventory.services import record_movement

ZERO = Decimal('0.000')
DEFAULT_NOTES = 'Carga inicial de existencia.'


class Command(BaseCommand):
    help = 'Registra una entrada de inventario por producto para dejar el stock en positivo.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--min',
            type=int,
            default=1,
            dest='min_qty',
            help='Cantidad mínima por producto (por defecto 1).',
        )
        parser.add_argument(
            '--max',
            type=int,
            default=10,
            dest='max_qty',
            help='Cantidad máxima por producto (por defecto 10).',
        )
        parser.add_argument(
            '--include-filled',
            action='store_true',
            help='También suma a los productos que ya tienen existencia. Por defecto solo toca los que están en cero.',
        )
        parser.add_argument(
            '--user',
            help='Username que figura como responsable. Por defecto, el primer superusuario.',
        )
        parser.add_argument(
            '--seed',
            type=int,
            help='Semilla para reproducir la misma distribución de cantidades.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué cambiaría sin escribir nada.',
        )

    def handle(self, *args, **options):
        min_qty = options['min_qty']
        max_qty = options['max_qty']
        if min_qty < 1 or max_qty < 1:
            raise CommandError('Las cantidades deben ser mayores que cero.')
        if min_qty > max_qty:
            raise CommandError('--min no puede ser mayor que --max.')

        user = self._resolve_user(options['user'])
        queryset = Product.objects.all().order_by('code')
        if not options['include_filled']:
            queryset = queryset.filter(stock=ZERO)

        if not queryset.exists():
            self.stdout.write('No hay productos que cargar. Nada que hacer.')
            return

        random_source = random.Random(options['seed'])
        plan = [
            (product, random_source.randint(min_qty, max_qty)) for product in queryset
        ]
        total_units = sum(quantity for _, quantity in plan)

        self.stdout.write(
            f'Productos: {len(plan)} | unidades totales: {total_units} '
            f'| rango: {min_qty}-{max_qty} | responsable: {user.username}'
        )
        if options['dry_run']:
            for product, quantity in plan:
                self.stdout.write(f'  {product.code}  +{quantity}  stock {product.stock} -> {Decimal(quantity) + product.stock}')
            self.stdout.write(self.style.WARNING('Simulación: no se escribió nada.'))
            return

        with transaction.atomic():
            for product, quantity in plan:
                record_movement(
                    product_id=product.pk,
                    movement_type=StockMovement.MovementType.IN,
                    origin=StockMovement.Origin.ENTRADA,
                    origin_id=None,
                    quantity=quantity,
                    user=user,
                    unit_cost_usd=None,
                    notes=DEFAULT_NOTES,
                    occurred_at=timezone.now(),
                )

        remaining_zero = Product.objects.filter(stock=ZERO).count()
        self.stdout.write(
            self.style.SUCCESS(f'Existencia cargada. Productos aún en cero: {remaining_zero}.')
        )
        if remaining_zero:
            self.stdout.write(
                self.style.WARNING(
                    'Quedan productos en cero. Usa --include-filled si también quieres sumarles.'
                )
            )

    def _resolve_user(self, username: str | None):
        model = get_user_model()
        if username:
            user = model.objects.filter(username=username).first()
            if user is None:
                raise CommandError(f'No existe el usuario "{username}".')
            return user
        user = model.objects.filter(is_superuser=True).order_by('id').first()
        if user is None:
            raise CommandError('No hay superusuario para atribuir la carga.')
        return user
