"""Shared test helpers."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.utils import timezone
from rest_framework.test import APITestCase

from catalog.models import Product
from core.enums import CURRENCY_USD
from core.roles import GROUP_NAMES
from core.services import sync_role_groups
from rates.models import ExchangeRate

DEFAULT_RATE = Decimal('36.5000')


class DomainTestCase(APITestCase):
    """Base case with roles, a current rate and a sample product."""

    def setUp(self):
        super().setUp()
        sync_role_groups()
        self.admin = self._make_user('admin', is_superuser=True)
        self.manager = self._make_user('manager', GROUP_NAMES['GERENTE'])
        self.warehouse = self._make_user('warehouse', GROUP_NAMES['ALMACENERO'])
        self.cashier = self._make_user('cashier', GROUP_NAMES['CAJERO'])
        self.rate = ExchangeRate.objects.create(
            rate=DEFAULT_RATE,
            effective_date=timezone.localdate(),
            source=ExchangeRate.Source.BCV,
        )
        self.product = Product.objects.create(
            name='Tostones picantes con limón TOM 270G',
            brand='Mayu',
            cost_usd=Decimal('2.10'),
            price_usd=Decimal('3.50'),
        )

    def _make_user(self, username: str, role: str | None = None, is_superuser: bool = False) -> User:
        user = User.objects.create_user(
            username=username,
            password='testpass123',
            is_superuser=is_superuser,
            is_staff=is_superuser,
        )
        if role:
            group, _ = Group.objects.get_or_create(name=GROUP_NAMES[role])
            user.groups.add(group)
        return user

    def change_rate(self, rate: Decimal, days_ago: int = 0) -> ExchangeRate:
        exchange_rate, _ = ExchangeRate.objects.update_or_create(
            source=ExchangeRate.Source.BCV,
            effective_date=timezone.localdate() - timedelta(days=days_ago),
            defaults={'rate': rate},
        )
        return exchange_rate

    def as_user(self, user: User) -> None:
        self.client.force_authenticate(user=user)
