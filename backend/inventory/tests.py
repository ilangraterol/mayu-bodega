from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from catalog.models import Product
from core.enums import CURRENCY_USD
from core.money import usd_to_ves, ves_to_usd
from inventory.models import ExitNote, ExitNoteReason, GoodsEntry, StockMovement
from inventory.services import (
    InsufficientStockError,
    cancel_entry,
    cancel_exit_note,
    moment_on,
    record_movement,
    register_entry,
    register_exit_note,
)
from rates.models import ExchangeRate


class EntryTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        self.user = User.objects.create_user(username='almacenero', password='x')
        self.product = Product.objects.create(
            name='Aceite vegetal 1L', cost_usd=Decimal('1.00'), price_usd=Decimal('1.60')
        )
        ExchangeRate.objects.create(
            rate=Decimal('36.5000'), effective_date=timezone.localdate(), source=ExchangeRate.Source.BCV
        )

    def test_entry_increases_stock_and_creates_movement(self):
        entry = register_entry(
            user=self.user,
            entry_date=timezone.localdate(),
            currency=CURRENCY_USD,
            items=[{'product_id': self.product.pk, 'quantity': '24', 'unit_cost': '1.10'}],
            supplier_name='Distribuidora El Oriente',
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal('24.000'))
        self.assertEqual(self.product.cost_usd, Decimal('1.10'))
        self.assertEqual(entry.total_usd, Decimal('26.40'))
        self.assertEqual(entry.code, 'E000001')

        movement = StockMovement.objects.get()
        self.assertEqual(movement.movement_type, StockMovement.MovementType.IN)
        self.assertEqual(movement.origin, StockMovement.Origin.ENTRADA)
        self.assertEqual(movement.balance_after, Decimal('24.000'))
        self.assertEqual(movement.quantity, Decimal('24.000'))

    def test_entry_in_bolivars_converts_with_the_current_rate(self):
        entry = register_entry(
            user=self.user,
            entry_date=timezone.localdate(),
            currency='VES',
            items=[{'product_id': self.product.pk, 'quantity': '10', 'unit_cost': '36.50'}],
        )
        self.assertEqual(entry.rate_applied, Decimal('36.5000'))
        self.assertEqual(entry.total_usd, Decimal('10.00'))
        self.assertEqual(entry.items.get().unit_cost_usd, Decimal('1.00'))

    def test_entry_rejects_non_positive_values(self):
        with self.assertRaises(ValidationError):
            register_entry(
                user=self.user,
                entry_date=timezone.localdate(),
                currency=CURRENCY_USD,
                items=[{'product_id': self.product.pk, 'quantity': '0', 'unit_cost': '1.00'}],
            )

    def test_cancelling_an_entry_appends_reversing_movements(self):
        register_entry(
            user=self.user,
            entry_date=timezone.localdate(),
            currency=CURRENCY_USD,
            items=[{'product_id': self.product.pk, 'quantity': '10', 'unit_cost': '1.00'}],
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal('10.000'))

        entry = GoodsEntry.objects.get()
        cancel_entry(user=self.user, entry=entry, reason='Mercancía dañada en tránsito')

        self.product.refresh_from_db()
        entry.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal('0.000'))
        self.assertTrue(entry.is_cancelled)
        self.assertEqual(StockMovement.objects.count(), 2)
        self.assertEqual(
            StockMovement.objects.order_by('id').last().movement_type, StockMovement.MovementType.OUT
        )


class ExitNoteTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User

        self.user = User.objects.create_user(username='almacenero', password='x')
        self.product = Product.objects.create(
            name='Harina de trigo 1kg', cost_usd=Decimal('0.80'), price_usd=Decimal('1.20')
        )
        self.product.stock = Decimal('5.000')
        self.product.save(update_fields=['stock'])

    def test_exit_note_deducts_stock(self):
        note = register_exit_note(
            user=self.user,
            exit_date=timezone.localdate(),
            reason=ExitNoteReason.MERMA,
            description='Producto aplastado en el estante',
            items=[{'product_id': self.product.pk, 'quantity': '2'}],
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal('3.000'))
        self.assertEqual(note.total_units, Decimal('2.000'))
        self.assertEqual(note.code, 'S000001')

    def test_exit_note_cannot_create_negative_stock(self):
        with self.assertRaises(InsufficientStockError):
            register_exit_note(
                user=self.user,
                exit_date=timezone.localdate(),
                reason=ExitNoteReason.PERDIDA,
                description='Pérdida total de la mercancía',
                items=[{'product_id': self.product.pk, 'quantity': '9'}],
            )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal('5.000'))
        self.assertEqual(StockMovement.objects.count(), 0)
        self.assertEqual(ExitNote.objects.count(), 0)

    def test_exit_note_requires_description(self):
        with self.assertRaises(ValidationError):
            register_exit_note(
                user=self.user,
                exit_date=timezone.localdate(),
                reason=ExitNoteReason.MERMA,
                description='  ',
                items=[{'product_id': self.product.pk, 'quantity': '1'}],
            )

    def test_cancelling_an_exit_note_restores_stock(self):
        note = register_exit_note(
            user=self.user,
            exit_date=timezone.localdate(),
            reason=ExitNoteReason.MERMA,
            description='Rotura durante el acomodo',
            items=[{'product_id': self.product.pk, 'quantity': '2'}],
        )
        cancel_exit_note(user=self.user, note=note, reason='Error de registro')

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal('5.000'))
        self.assertEqual(StockMovement.objects.count(), 2)


class StockMovementImmutabilityTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(name='Detergente', cost_usd=Decimal('2.00'), price_usd=Decimal('3.00'))
        self.movement = StockMovement.objects.create(
            product=self.product,
            movement_type=StockMovement.MovementType.IN,
            origin=StockMovement.Origin.ANULACION,
            quantity=Decimal('5.000'),
            balance_after=Decimal('5.000'),
            occurred_at=timezone.now(),
        )

    def test_movement_cannot_be_updated(self):
        self.movement.quantity = Decimal('9.000')
        with self.assertRaises(ValidationError):
            self.movement.save()

    def test_movement_cannot_be_deleted(self):
        with self.assertRaises(ValidationError):
            self.movement.delete()


class PendingUnitsTests(TestCase):
    """The ledger invariant: ``sum(signed movements) == stock - pending_units``."""

    def setUp(self):
        from django.contrib.auth.models import User

        self.user = User.objects.create_user(username='cajero', password='x')
        self.product = Product.objects.create(
            name='Atún en lata 170G', cost_usd=Decimal('1.50'), price_usd=Decimal('2.40')
        )
        ExchangeRate.objects.create(
            rate=Decimal('36.5000'), effective_date=timezone.localdate(), source=ExchangeRate.Source.BCV
        )

    def _out(self, quantity, allow_shortage=False):
        return record_movement(
            product_id=self.product.pk,
            movement_type=StockMovement.MovementType.OUT,
            origin=StockMovement.Origin.VENTA,
            origin_id=1,
            quantity=quantity,
            user=self.user,
            allow_shortage=allow_shortage,
        )

    def _in(self, quantity):
        return record_movement(
            product_id=self.product.pk,
            movement_type=StockMovement.MovementType.IN,
            origin=StockMovement.Origin.ENTRADA,
            origin_id=1,
            quantity=quantity,
            user=self.user,
        )

    def _assert_ledger_reconciles(self):
        self.product.refresh_from_db()
        ledger = sum(
            (movement.signed_quantity for movement in self.product.movements.all()),
            Decimal('0.000'),
        )
        self.assertEqual(self.product.net_position, ledger)

    def test_shortage_becomes_pending_units_instead_of_negative_stock(self):
        self._out('4', allow_shortage=True)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal('0.000'))
        self.assertEqual(self.product.pending_units, Decimal('4.000'))
        self.assertEqual(self.product.net_position, Decimal('-4.000'))
        self._assert_ledger_reconciles()

    def test_shortage_is_refused_when_not_allowed(self):
        with self.assertRaises(InsufficientStockError):
            self._out('4')
        self.assertEqual(StockMovement.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.pending_units, Decimal('0.000'))

    def test_incoming_units_cancel_the_debt_before_raising_stock(self):
        self._out('6', allow_shortage=True)
        self._in('2')

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal('0.000'))
        self.assertEqual(self.product.pending_units, Decimal('4.000'))
        self._assert_ledger_reconciles()

    def test_surplus_incoming_units_become_stock(self):
        self._out('6', allow_shortage=True)
        self._in('10')

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal('4.000'))
        self.assertEqual(self.product.pending_units, Decimal('0.000'))
        self._assert_ledger_reconciles()

    def test_exit_notes_never_create_pending_units(self):
        self._in('5')
        with self.assertRaises(InsufficientStockError):
            record_movement(
                product_id=self.product.pk,
                movement_type=StockMovement.MovementType.OUT,
                origin=StockMovement.Origin.NOTA_SALIDA,
                origin_id=1,
                quantity='9',
                user=self.user,
            )
        self.product.refresh_from_db()
        self.assertEqual(self.product.pending_units, Decimal('0.000'))
        self._assert_ledger_reconciles()

    def test_movement_records_the_pending_balance_at_that_instant(self):
        self._out('3', allow_shortage=True)
        last = StockMovement.objects.order_by('id').last()
        self.assertEqual(last.balance_after, Decimal('0.000'))
        self.assertEqual(last.pending_after, Decimal('3.000'))
        self.assertEqual(last.net_position_after, Decimal('-3.000'))


class MoneyTests(TestCase):
    def test_conversions_use_decimal_and_half_up(self):
        self.assertEqual(usd_to_ves(Decimal('3.50'), Decimal('36.5000')), Decimal('127.75'))
        self.assertEqual(ves_to_usd(Decimal('127.75'), Decimal('36.5000')), Decimal('3.50'))

    def test_ves_to_usd_rejects_zero_rate(self):
        with self.assertRaises(ValueError):
            ves_to_usd(Decimal('100'), Decimal('0'))


class MomentOnTests(TestCase):
    def test_moment_on_is_timezone_aware(self):
        moment = moment_on(timezone.localdate())
        self.assertIsNotNone(moment.tzinfo)


class SeedStockTests(TestCase):
    """The seed command must go through the ledger, never write stock directly."""

    def setUp(self):
        from django.contrib.auth.models import User

        self.user = User.objects.create_superuser(username='seedadmin', password='x', email='')
        self.empty = Product.objects.create(
            name='Arroz 1 Kg', cost_usd=Decimal('0.00'), price_usd=Decimal('1.20')
        )
        self.filled = Product.objects.create(
            name='Aceite 1L', cost_usd=Decimal('1.00'), price_usd=Decimal('1.60')
        )
        record_movement(
            product_id=self.filled.pk,
            movement_type=StockMovement.MovementType.IN,
            origin=StockMovement.Origin.ENTRADA,
            origin_id=None,
            quantity='40',
            user=self.user,
        )

    def _run(self, *args):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command('seed_stock', *args, stdout=out, stderr=out)
        return out.getvalue()

    def test_makes_every_empty_product_positive_within_the_range(self):
        self._run('--min', '1', '--max', '10', '--seed', '7')

        self.empty.refresh_from_db()
        self.assertGreaterEqual(self.empty.stock, Decimal('1.000'))
        self.assertLessEqual(self.empty.stock, Decimal('10.000'))

    def test_does_not_touch_products_that_already_have_stock(self):
        self._run('--seed', '7')

        self.filled.refresh_from_db()
        self.assertEqual(self.filled.stock, Decimal('40.000'))

    def test_include_filled_adds_on_top_of_the_existing_stock(self):
        self._run('--include-filled', '--min', '5', '--max', '5', '--seed', '7')

        self.filled.refresh_from_db()
        self.assertEqual(self.filled.stock, Decimal('45.000'))

    def test_leaves_cost_usd_untouched(self):
        self._run('--seed', '7')

        self.empty.refresh_from_db()
        self.assertEqual(self.empty.cost_usd, Decimal('0.00'))

    def test_records_an_auditable_incoming_movement_without_a_cost(self):
        self._run('--min', '3', '--max', '3', '--seed', '7')

        movement = StockMovement.objects.get(product_id=self.empty.pk)
        self.assertEqual(movement.movement_type, StockMovement.MovementType.IN)
        self.assertEqual(movement.origin, StockMovement.Origin.ENTRADA)
        self.assertEqual(movement.quantity, Decimal('3.000'))
        self.assertIsNone(movement.unit_cost_usd)
        self.assertEqual(movement.created_by, self.user)
        # `record_movement` writes the balance with a queryset update, so the
        # in-memory instance is stale until it is refreshed.
        self.empty.refresh_from_db()
        self.assertEqual(movement.balance_after, self.empty.stock)

    def test_is_idempotent_by_default(self):
        self._run('--seed', '7')
        self.empty.refresh_from_db()
        first = self.empty.stock
        output = self._run('--seed', '7')

        self.empty.refresh_from_db()
        self.assertEqual(self.empty.stock, first)
        self.assertIn('No hay productos que cargar', output)

    def test_dry_run_writes_nothing(self):
        self._run('--dry-run', '--seed', '7')

        self.empty.refresh_from_db()
        self.assertEqual(self.empty.stock, Decimal('0.000'))
        self.assertEqual(StockMovement.objects.filter(product_id=self.empty.pk).count(), 0)

    def test_preserves_the_ledger_invariant(self):
        self._run('--include-filled', '--seed', '7')

        for product in Product.objects.all():
            signed = sum(
                (
                    movement.signed_quantity
                    for movement in StockMovement.objects.filter(product_id=product.pk)
                ),
                Decimal('0'),
            )
            self.assertEqual(signed, product.net_position, f'descuadre en {product.code}')

    def test_rejects_an_inverted_range(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            self._run('--min', '10', '--max', '1')
