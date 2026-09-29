"""Populate the database with realistic demo data for local development.

The command is idempotent: products are matched by name, users by username and
customers by document id, so it can be re-run safely after adding items.
"""

import os
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

import inventory.services as inventory_services
import sales.services as sales_services
from catalog.models import (
    UNIT_CAJA,
    UNIT_KILO,
    UNIT_LIBRA,
    UNIT_UNIDAD,
    Product,
)
from core.enums import CURRENCY_USD
from core.models import StoreConfig
from core.roles import GROUP_NAMES, ROLE_ADMIN, ROLE_CASHIER, ROLE_MANAGER, ROLE_WAREHOUSE
from core.services import sync_role_groups
from customers.models import Customer
from rates.models import ExchangeRate
from rates.services import register_manual_rate
from sales.models import PaymentMethod, SaleStatus, SaleType

# Development convenience only. Outside local work set MAYU_DEMO_PASSWORD so a
# seeded account never ships with a well known password.
DEMO_PASSWORD = os.environ.get('MAYU_DEMO_PASSWORD', 'mayu1234')

USERS = [
    ('admin', 'Administrador', ROLE_ADMIN),
    ('gerente', 'Gerente', ROLE_MANAGER),
    ('almacenero', 'Almacenero', ROLE_WAREHOUSE),
    ('cajero', 'Cajero', ROLE_CASHIER),
]

PRODUCTS = [
    {
        'name': 'Tostones picantes con limón TOM 270G',
        'brand': 'Mayu',
        'unit_of_measure': UNIT_UNIDAD,
        'barcode': '7591001000011',
        'cost_usd': '1.85',
        'price_usd': '3.00',
    },
    {
        'name': 'Arroz blanco 5kg',
        'brand': 'Don Pedro',
        'unit_of_measure': UNIT_LIBRA,
        'units_per_package': 10,
        'barcode': '7591001000028',
        'cost_usd': '9.40',
        'price_usd': '13.50',
    },
    {
        'name': 'Aceite vegetal 1L',
        'brand': 'Girasol',
        'unit_of_measure': UNIT_UNIDAD,
        'barcode': '7591001000035',
        'cost_usd': '1.20',
        'price_usd': '1.90',
    },
    {
        'name': 'Azúcar 1kg',
        'brand': 'Bugalú',
        'unit_of_measure': UNIT_KILO,
        'barcode': '7591001000042',
        'cost_usd': '0.75',
        'price_usd': '1.20',
    },
    {
        'name': 'Detergente en polvo 5kg',
        'brand': 'Ariel',
        'unit_of_measure': UNIT_UNIDAD,
        'barcode': '7591001000059',
        'cost_usd': '7.10',
        'price_usd': '10.00',
    },
    {
        'name': 'Pasta corta 500g',
        'brand': 'Doria',
        'unit_of_measure': UNIT_UNIDAD,
        'barcode': '7591001000066',
        'cost_usd': '0.90',
        'price_usd': '1.50',
    },
    {
        'name': 'Café molido 500g',
        'brand': 'Bustelo',
        'unit_of_measure': UNIT_UNIDAD,
        'barcode': '7591001000073',
        'cost_usd': '3.30',
        'price_usd': '5.20',
    },
    {
        'name': 'Agua mineral PET 1.5L',
        'brand': 'Brimart',
        'unit_of_measure': UNIT_CAJA,
        'units_per_package': 12,
        'barcode': '7591001000080',
        'cost_usd': '0.42',
        'price_usd': '0.70',
    },
    {
        'name': 'Harina de trigo 1kg',
        'brand': 'Puig',
        'unit_of_measure': UNIT_KILO,
        'barcode': '7591001000097',
        'cost_usd': '0.65',
        'price_usd': '1.05',
    },
    {
        'name': 'Atún en lata 170g',
        'brand': 'Van Camps',
        'unit_of_measure': UNIT_UNIDAD,
        'barcode': '7591001000103',
        'cost_usd': '1.55',
        'price_usd': '2.40',
    },
]

CUSTOMERS = [
    {'document_id': 'V-12345678', 'name': 'María González', 'phone': '0412-1234567', 'address': 'Av. Bolívar, Catia'},
    {'document_id': 'V-23456789', 'name': 'José Ramírez', 'phone': '0414-2345678', 'address': 'Urb. Los Pinos, casa 12'},
    {'document_id': 'V-34567890', 'name': 'Carmen Osorio', 'phone': '0424-3456789', 'address': 'Los Teques, Cúa'},
    {'document_id': 'V-45678901', 'name': 'Pedro Márquez', 'phone': '0416-4567890', 'address': 'Petare, Av. Miranda'},
    {'document_id': 'V-56789012', 'name': 'Rosa Williams', 'phone': '0412-5678901', 'address': 'Chacao, Calle Principal'},
]

RATE_HISTORY = [
    (7, Decimal('36.8500')),
    (5, Decimal('37.1000')),
    (3, Decimal('37.4000')),
    (1, Decimal('37.6500')),
    (0, Decimal('37.9000')),
]


class Command(BaseCommand):
    help = 'Carga datos de demostración (usuarios, catálogo, tasa, clientes, ventas).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush-sales',
            action='store_true',
            help='Anula las ventas de demostración anteriores antes de recargar.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        sync_role_groups()
        admin = self._create_users()
        self._create_rates(admin)
        products = self._create_products()
        customers = self._create_customers()
        self._create_stock(products, admin)
        self._create_sales(products, customers, admin, options['flush_sales'])
        StoreConfig.load()

        self.stdout.write(self.style.SUCCESS('Datos de demostración cargados.'))
        self.stdout.write(f'Usuarios: {[u[0] for u in USERS]} · contraseña: {DEMO_PASSWORD}')
        self.stdout.write(f'Productos: {len(products)} · Clientes: {len(customers)}')

    def _create_users(self) -> User:
        admin = None
        for username, full_name, role_key in USERS:
            group = Group.objects.get(name=GROUP_NAMES[role_key])
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={'first_name': full_name},
            )
            user.first_name = full_name
            user.last_name = ''
            user.email = ''
            user.is_active = True
            user.is_staff = role_key == ROLE_ADMIN
            user.is_superuser = role_key == ROLE_ADMIN
            user.set_password(DEMO_PASSWORD)
            user.save()
            user.groups.set([group])
            if role_key == ROLE_ADMIN:
                admin = user
        return admin

    def _create_rates(self, admin: User) -> None:
        today = timezone.localdate()
        for days_ago, rate in RATE_HISTORY:
            day = today - timedelta(days=days_ago)
            ExchangeRate.objects.update_or_create(
                source=ExchangeRate.Source.BCV,
                effective_date=day,
                defaults={'rate': rate, 'is_active': True},
            )
        if not ExchangeRate.objects.filter(source=ExchangeRate.Source.MANUAL).exists():
            register_manual_rate(
                rate=Decimal('38.2500'),
                effective_date=today,
                user=admin,
                notes='Tasa manual de respaldo cargada por el comando de demostración.',
            )

    def _create_products(self) -> list[Product]:
        products = []
        for payload in PRODUCTS:
            data = dict(payload)
            data['cost_usd'] = Decimal(data['cost_usd'])
            data['price_usd'] = Decimal(data['price_usd'])
            product, _ = Product.objects.update_or_create(name=data.pop('name'), defaults=data)
            products.append(product)
        return products

    def _create_customers(self) -> list[Customer]:
        customers = []
        for payload in CUSTOMERS:
            customer, _ = Customer.objects.update_or_create(
                document_id=payload['document_id'],
                defaults={k: v for k, v in payload.items() if k != 'document_id'},
            )
            customers.append(customer)
        return customers

    def _create_stock(self, products: list[Product], admin: User) -> None:
        from inventory.models import StockMovement

        if StockMovement.objects.filter(origin=StockMovement.Origin.ENTRADA).exists():
            return

        items = []
        for index, product in enumerate(products):
            quantity = 120 if index % 3 == 0 else 48
            items.append({'product_id': product.pk, 'quantity': str(quantity), 'unit_cost': str(product.cost_usd)})

        inventory_services.register_entry(
            user=admin,
            entry_date=timezone.localdate() - timedelta(days=7),
            supplier_name='Distribuidora Mayu C.A.',
            items=items,
            notes='Carga inicial de inventario.',
        )
        self.stdout.write(f'Entrada de inventario: {len(items)} artículos.')

    def _create_sales(
        self,
        products: list[Product],
        customers: list[Customer],
        admin: User,
        flush_sales: bool,
    ) -> None:
        from sales.models import Sale

        existing = Sale.objects.count()
        if existing:
            if flush_sales:
                for sale in Sale.objects.exclude(status=SaleStatus.ANULLED):
                    sales_services.void_sale(user=admin, sale=sale, reason='Recarga de demo')
                self.stdout.write('Ventas anteriores anuladas.')
            else:
                self.stdout.write(f'Ya existen {existing} ventas; se omite la carga de ventas.')
                return

        sales_services.create_sale(
            user=admin,
            items=[
                {'product_id': products[0].pk, 'quantity': '3'},
                {'product_id': products[2].pk, 'quantity': '2'},
            ],
            sale_type=SaleType.PAID,
            currency=CURRENCY_USD,
            paid_amount=Decimal('12.80'),
            payment_method=PaymentMethod.CASH_USD,
            notes='Venta de mostrador.',
        )

        credit_sale = sales_services.create_sale(
            user=admin,
            items=[{'product_id': products[4].pk, 'quantity': '2'}],
            sale_type=SaleType.CREDIT,
            customer=customers[0],
            currency=CURRENCY_USD,
            notes='Fiado de la semana.',
        )

        sales_services.register_payment(
            user=admin,
            debt=credit_sale.debt,
            amount=Decimal('5.00'),
            currency=CURRENCY_USD,
            method=PaymentMethod.CASH_USD,
            notes='Abono parcial.',
        )

        sales_services.create_sale(
            user=admin,
            items=[{'product_id': products[8].pk, 'quantity': '10'}],
            sale_type=SaleType.CREDIT,
            customer=customers[1],
            currency=CURRENCY_USD,
        )
        self.stdout.write('Ventas de demostración: 1 pagada, 2 fiadas, 1 abono.')
