from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from catalog.models import Product
from core.enums import CURRENCY_USD
from core.models import StoreConfig
from customers.models import Customer
from inventory.models import StockMovement
from inventory.services import register_entry
from rates.models import ExchangeRate
from sales.models import CustomerDebt, DebtPayment, DebtStatus, PaymentMethod, Sale, SaleStatus, SaleType
from sales.services import create_sale, register_payment, void_payment, void_sale

PRICE = Decimal('3.50')


class SaleTestCaseMixin:
    def make_product(self, stock: str = '0', price: str = '3.50') -> Product:
        product = Product.objects.create(
            name=f'Producto {Product.objects.count() + 1}',
            cost_usd=Decimal('2.00'),
            price_usd=Decimal(price),
        )
        if Decimal(stock) > 0:
            register_entry(
                user=self.user,
                entry_date=timezone.localdate(),
                currency=CURRENCY_USD,
                items=[{'product_id': product.pk, 'quantity': stock, 'unit_cost': '2.00'}],
            )
            product.refresh_from_db()
        return product

    def make_customer(self, name: str = 'María Pérez') -> Customer:
        return Customer.objects.create(document_id='V-12345678', name=name)

    def change_rate(self, rate: Decimal, days_ago: int = 0) -> ExchangeRate:
        exchange_rate, _ = ExchangeRate.objects.update_or_create(
            source=ExchangeRate.Source.BCV,
            effective_date=timezone.localdate() - timedelta(days=days_ago),
            defaults={'rate': rate},
        )
        return exchange_rate

    def make_rate(self, rate: Decimal = Decimal('36.5000')) -> ExchangeRate:
        return self.change_rate(rate)


class PaidSaleTests(SaleTestCaseMixin, TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        self.user = User.objects.create_user(username='cajero', password='x')
        self.make_rate()
        self.product = self.make_product(stock='10')
        StoreConfig.load()

    def test_paid_sale_deducts_stock_and_records_movement(self):
        sale = create_sale(
            user=self.user,
            items=[{'product_id': self.product.pk, 'quantity': '3'}],
            sale_type=SaleType.PAID,
            paid_amount=Decimal('10.50'),
            payment_method=PaymentMethod.CASH_USD,
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal('7.000'))
        self.assertEqual(sale.total_usd, Decimal('10.50'))
        self.assertEqual(sale.subtotal_usd, Decimal('10.50'))
        self.assertEqual(sale.paid_amount, Decimal('10.50'))
        self.assertEqual(sale.amount_due_usd, Decimal('0.00'))
        self.assertFalse(CustomerDebt.objects.exists())
        self.assertEqual(StockMovement.objects.filter(origin=StockMovement.Origin.VENTA).count(), 1)

    def test_sale_without_enough_stock_is_blocked(self):
        with self.assertRaises(ValidationError):
            create_sale(
                user=self.user,
                items=[{'product_id': self.product.pk, 'quantity': '25'}],
                sale_type=SaleType.PAID,
                paid_amount=Decimal('100.00'),
            )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal('10.000'))
        self.assertFalse(Sale.objects.exists())

    def test_zero_stock_sale_is_blocked_by_default(self):
        empty = self.make_product(stock='0')
        with self.assertRaises(ValidationError):
            create_sale(
                user=self.user,
                items=[{'product_id': empty.pk, 'quantity': '2'}],
                sale_type=SaleType.PAID,
                paid_amount=Decimal('10.00'),
            )

    def test_zero_stock_sale_is_allowed_when_the_switch_is_on(self):
        config = StoreConfig.load()
        config.allow_zero_stock_sale = True
        config.save(update_fields=['allow_zero_stock_sale'])
        empty = self.make_product(stock='0')

        sale = create_sale(
            user=self.user,
            items=[{'product_id': empty.pk, 'quantity': '2'}],
            sale_type=SaleType.PAID,
            paid_amount=Decimal('10.00'),
        )
        self.assertEqual(sale.items.get().quantity, Decimal('2.000'))
        empty.refresh_from_db()
        self.assertEqual(empty.stock, Decimal('0.000'))  # never negative
        self.assertEqual(empty.pending_units, Decimal('2.000'))  # owed to the store
        self.assertEqual(empty.net_position, Decimal('-2.000'))

    def test_incoming_stock_clears_the_inventory_debt_first(self):
        config = StoreConfig.load()
        config.allow_zero_stock_sale = True
        config.save(update_fields=['allow_zero_stock_sale'])
        empty = self.make_product(stock='0')

        create_sale(
            user=self.user,
            items=[{'product_id': empty.pk, 'quantity': '2'}],
            sale_type=SaleType.PAID,
            paid_amount=Decimal('10.00'),
        )
        register_entry(
            user=self.user,
            entry_date=timezone.localdate(),
            currency=CURRENCY_USD,
            items=[{'product_id': empty.pk, 'quantity': '10', 'unit_cost': '2.00'}],
        )

        empty.refresh_from_db()
        self.assertEqual(empty.pending_units, Decimal('0.000'))
        self.assertEqual(empty.stock, Decimal('8.000'))  # 10 received - 2 owed
        self.assertEqual(empty.net_position, Decimal('8.000'))

    def test_partial_replenishment_keeps_the_remaining_debt(self):
        config = StoreConfig.load()
        config.allow_zero_stock_sale = True
        config.save(update_fields=['allow_zero_stock_sale'])
        empty = self.make_product(stock='0')

        create_sale(
            user=self.user,
            items=[{'product_id': empty.pk, 'quantity': '5'}],
            sale_type=SaleType.PAID,
            paid_amount=Decimal('20.00'),
        )
        register_entry(
            user=self.user,
            entry_date=timezone.localdate(),
            currency=CURRENCY_USD,
            items=[{'product_id': empty.pk, 'quantity': '3', 'unit_cost': '2.00'}],
        )

        empty.refresh_from_db()
        self.assertEqual(empty.stock, Decimal('0.000'))
        self.assertEqual(empty.pending_units, Decimal('2.000'))
        self.assertEqual(empty.net_position, Decimal('-2.000'))

    def test_ledger_always_reconciles_with_stock_minus_pending(self):
        product = self.product
        # setUp already received 10 units, so the ledger starts at 10.
        ledger = Decimal('10.000')
        self.assertEqual(product.net_position, ledger)

        create_sale(
            user=self.user,
            items=[{'product_id': product.pk, 'quantity': '3'}],
            sale_type=SaleType.PAID,
            paid_amount=Decimal('10.50'),
        )
        ledger -= Decimal('3.000')

        product.refresh_from_db()
        self.assertEqual(product.net_position, ledger)

        register_entry(
            user=self.user,
            entry_date=timezone.localdate(),
            currency=CURRENCY_USD,
            items=[{'product_id': product.pk, 'quantity': '4', 'unit_cost': '2.00'}],
        )
        ledger += Decimal('4.000')

        product.refresh_from_db()
        self.assertEqual(product.net_position, ledger)

    def test_a_second_zero_stock_sale_accumulates_the_debt(self):
        config = StoreConfig.load()
        config.allow_zero_stock_sale = True
        config.save(update_fields=['allow_zero_stock_sale'])
        empty = self.make_product(stock='0')

        create_sale(
            user=self.user,
            items=[{'product_id': empty.pk, 'quantity': '2'}],
            sale_type=SaleType.PAID,
            paid_amount=Decimal('10.00'),
        )
        create_sale(
            user=self.user,
            items=[{'product_id': empty.pk, 'quantity': '3'}],
            sale_type=SaleType.PAID,
            paid_amount=Decimal('15.00'),
        )

        empty.refresh_from_db()
        self.assertEqual(empty.stock, Decimal('0.000'))
        self.assertEqual(empty.pending_units, Decimal('5.000'))
        self.assertEqual(empty.net_position, Decimal('-5.000'))
        self.assertEqual(
            StockMovement.objects.filter(
                product=empty, movement_type=StockMovement.MovementType.OUT
            ).count(),
            2,
        )

    def test_underpaid_sale_is_rejected(self):
        with self.assertRaises(ValidationError):
            create_sale(
                user=self.user,
                items=[{'product_id': self.product.pk, 'quantity': '3'}],
                sale_type=SaleType.PAID,
                paid_amount=Decimal('5.00'),
            )

    def test_surcharge_percentage_is_applied_from_the_store_config(self):
        config = StoreConfig.load()
        config.default_surcharge_percentage = Decimal('10.00')
        config.save(update_fields=['default_surcharge_percentage'])

        sale = create_sale(
            user=self.user,
            items=[{'product_id': self.product.pk, 'quantity': '2'}],
            sale_type=SaleType.PAID,
            paid_amount=Decimal('7.70'),
        )
        self.assertEqual(sale.subtotal_usd, Decimal('7.00'))
        self.assertEqual(sale.surcharge_usd, Decimal('0.70'))
        self.assertEqual(sale.total_usd, Decimal('7.70'))
        self.assertEqual(sale.surcharge_percentage, Decimal('10.00'))

    def test_rate_is_frozen_on_the_sale(self):
        sale = create_sale(
            user=self.user,
            items=[{'product_id': self.product.pk, 'quantity': '1'}],
            sale_type=SaleType.PAID,
            paid_amount=Decimal('3.50'),
        )
        self.assertEqual(sale.exchange_rate_applied, Decimal('36.5000'))
        self.assertEqual(sale.total_ves, Decimal('127.75'))


class CreditSaleTests(SaleTestCaseMixin, TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        self.user = User.objects.create_user(username='cajero', password='x')
        self.make_rate()
        self.product = self.make_product(stock='20')
        self.customer = self.make_customer()

    def test_credit_sale_requires_a_customer(self):
        with self.assertRaises(ValidationError):
            create_sale(
                user=self.user,
                items=[{'product_id': self.product.pk, 'quantity': '1'}],
                sale_type=SaleType.CREDIT,
            )

    def test_credit_sale_opens_a_debt_in_usd(self):
        sale = create_sale(
            user=self.user,
            items=[{'product_id': self.product.pk, 'quantity': '2'}],
            sale_type=SaleType.CREDIT,
            customer=self.customer,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal('18.000'))
        self.assertEqual(sale.amount_due_usd, Decimal('7.00'))

        debt = CustomerDebt.objects.get()
        self.assertEqual(debt.customer, self.customer)
        self.assertEqual(debt.original_amount_usd, Decimal('7.00'))
        self.assertEqual(debt.balance_usd, Decimal('7.00'))
        self.assertEqual(debt.status, DebtStatus.OPEN)

    def test_credit_sale_to_inactive_customer_is_rejected(self):
        self.customer.is_active = False
        self.customer.save(update_fields=['is_active'])
        with self.assertRaises(ValidationError):
            create_sale(
                user=self.user,
                items=[{'product_id': self.product.pk, 'quantity': '1'}],
                sale_type=SaleType.CREDIT,
                customer=self.customer,
            )


class DebtPaymentTests(SaleTestCaseMixin, TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        self.user = User.objects.create_user(username='cajero', password='x')
        self.make_rate()
        self.product = self.make_product(stock='20')
        self.customer = self.make_customer()
        self.sale = create_sale(
            user=self.user,
            items=[{'product_id': self.product.pk, 'quantity': '2'}],
            sale_type=SaleType.CREDIT,
            customer=self.customer,
        )
        self.debt = CustomerDebt.objects.get()

    def test_payment_in_bolivars_uses_the_rate_of_the_payment_day(self):
        self.change_rate(Decimal('40.0000'))

        payment = register_payment(
            user=self.user,
            debt=self.debt,
            amount=Decimal('280.00'),
            currency='VES',
            method=PaymentMethod.CASH_VES,
        )
        self.debt.refresh_from_db()

        self.assertEqual(payment.exchange_rate_applied, Decimal('40.0000'))
        self.assertEqual(payment.amount_usd, Decimal('7.00'))
        self.assertEqual(self.debt.balance_usd, Decimal('0.00'))
        self.assertEqual(self.debt.status, DebtStatus.PAID)

    def test_partial_payment_keeps_the_debt_open(self):
        payment = register_payment(
            user=self.user,
            debt=self.debt,
            amount=Decimal('3.50'),
            currency=CURRENCY_USD,
            method=PaymentMethod.CASH_USD,
        )
        self.debt.refresh_from_db()
        self.assertEqual(payment.amount_usd, Decimal('3.50'))
        self.assertEqual(self.debt.balance_usd, Decimal('3.50'))
        self.assertEqual(self.debt.status, DebtStatus.OPEN)

    def test_payment_cannot_exceed_the_pending_balance(self):
        with self.assertRaises(ValidationError):
            register_payment(
                user=self.user,
                debt=self.debt,
                amount=Decimal('20.00'),
                currency=CURRENCY_USD,
                method=PaymentMethod.CASH_USD,
            )
        self.debt.refresh_from_db()
        self.assertEqual(self.debt.balance_usd, Decimal('7.00'))
        self.assertFalse(DebtPayment.objects.exists())

    def test_backdated_payment_uses_the_rate_of_its_own_date(self):
        self.change_rate(Decimal('40.0000'))  # today
        self.change_rate(Decimal('34.0000'), days_ago=2)  # the day the payment happened

        payment = register_payment(
            user=self.user,
            debt=self.debt,
            amount=Decimal('238.00'),
            currency='VES',
            method=PaymentMethod.CASH_VES,
            paid_at=timezone.now() - timedelta(days=2),
        )

        self.assertEqual(payment.exchange_rate_applied, Decimal('34.0000'))
        self.assertEqual(payment.amount_usd, Decimal('7.00'))
        self.debt.refresh_from_db()
        self.assertEqual(self.debt.status, DebtStatus.PAID)

    def test_payment_falls_back_to_the_last_known_rate_on_a_day_without_one(self):
        self.change_rate(Decimal('40.0000'))

        payment = register_payment(
            user=self.user,
            debt=self.debt,
            amount=Decimal('280.00'),
            currency='VES',
            method=PaymentMethod.CASH_VES,
            paid_at=timezone.now() - timedelta(days=3),
        )

        self.assertEqual(payment.exchange_rate_applied, Decimal('40.0000'))
        self.assertEqual(payment.amount_usd, Decimal('7.00'))

    def test_a_future_payment_cannot_be_registered(self):
        with self.assertRaises(ValidationError):
            register_payment(
                user=self.user,
                debt=self.debt,
                amount=Decimal('1.00'),
                currency=CURRENCY_USD,
                method=PaymentMethod.CASH_USD,
                paid_at=timezone.now() + timedelta(days=1),
            )

    def test_voided_payment_restores_the_balance(self):
        payment = register_payment(
            user=self.user,
            debt=self.debt,
            amount=Decimal('7.00'),
            currency=CURRENCY_USD,
            method=PaymentMethod.CASH_USD,
        )
        self.debt.refresh_from_db()
        self.assertEqual(self.debt.status, DebtStatus.PAID)

        void_payment(user=self.user, payment=payment, reason='Error de captura del cajero')
        self.debt.refresh_from_db()
        self.assertEqual(self.debt.balance_usd, Decimal('7.00'))
        self.assertEqual(self.debt.status, DebtStatus.OPEN)
        self.assertTrue(DebtPayment.objects.get().is_voided)

    def test_payments_cannot_be_deleted(self):
        payment = register_payment(
            user=self.user,
            debt=self.debt,
            amount=Decimal('1.00'),
            currency=CURRENCY_USD,
            method=PaymentMethod.CASH_USD,
        )
        with self.assertRaises(ValidationError):
            payment.delete()


class SaleVoidTests(SaleTestCaseMixin, TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        self.user = User.objects.create_user(username='cajero', password='x')
        self.make_rate()
        self.product = self.make_product(stock='10')
        self.customer = self.make_customer()

    def test_voiding_a_sale_restores_the_stock(self):
        sale = create_sale(
            user=self.user,
            items=[{'product_id': self.product.pk, 'quantity': '4'}],
            sale_type=SaleType.PAID,
            paid_amount=Decimal('14.00'),
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal('6.000'))

        void_sale(user=self.user, sale=sale, reason='Error de digitación del producto')
        self.product.refresh_from_db()
        sale.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal('10.000'))
        self.assertEqual(sale.status, SaleStatus.ANULLED)
        self.assertEqual(StockMovement.objects.filter(origin__in=['VENTA', 'ANULACION']).count(), 2)

    def test_voiding_a_sale_with_pending_debt_is_blocked(self):
        sale = create_sale(
            user=self.user,
            items=[{'product_id': self.product.pk, 'quantity': '2'}],
            sale_type=SaleType.CREDIT,
            customer=self.customer,
        )
        with self.assertRaises(ValidationError):
            void_sale(user=self.user, sale=sale, reason='Cliente devolvió la mercancía')
        sale.refresh_from_db()
        self.assertEqual(sale.status, SaleStatus.COMPLETED)

    def test_voiding_a_zero_stock_sale_clears_the_inventory_debt(self):
        config = StoreConfig.load()
        config.allow_zero_stock_sale = True
        config.save(update_fields=['allow_zero_stock_sale'])
        empty = self.make_product(stock='0')

        sale = create_sale(
            user=self.user,
            items=[{'product_id': empty.pk, 'quantity': '3'}],
            sale_type=SaleType.PAID,
            paid_amount=Decimal('12.00'),
        )
        empty.refresh_from_db()
        self.assertEqual(empty.pending_units, Decimal('3.000'))

        void_sale(user=self.user, sale=sale, reason='Error de digitación del cajero')

        empty.refresh_from_db()
        self.assertEqual(empty.stock, Decimal('0.000'))
        self.assertEqual(empty.pending_units, Decimal('0.000'))
        self.assertEqual(empty.net_position, Decimal('0.000'))
