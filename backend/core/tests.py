import io
import shutil
import tempfile
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

from catalog.models import Product, ProductImage
from catalog.image_processing import InvalidImageError
from core.enums import CURRENCY_USD
from core.models import StoreConfig
from core.testing import DomainTestCase
from customers.models import Customer
from inventory.models import GoodsEntry, ExitNote
from sales.models import CustomerDebt


def build_image_bytes(size=(800, 600), image_format='JPEG', color=(200, 40, 40)) -> bytes:
    buffer = io.BytesIO()
    Image.new('RGB', size, color).save(buffer, format=image_format)
    return buffer.getvalue()


class ProductImageTests(DomainTestCase):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp(prefix='mayu-test-media-')
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.media, True)

    def test_uploaded_image_is_converted_to_webp_with_a_thumbnail(self):
        upload = SimpleUploadedFile('foto.jpg', build_image_bytes(), content_type='image/jpeg')
        image = ProductImage.objects.create(product=self.product, image=upload)

        self.product.refresh_from_db()
        self.assertTrue(image.image.name.endswith('.webp'))
        self.assertTrue(image.thumbnail.name.endswith('.webp'))
        self.assertTrue(image.is_primary)
        self.assertLessEqual(max(image.width, image.height), 1200)
        self.assertLessEqual(max(image.thumbnail.width, image.thumbnail.height), 320)

        with Image.open(image.image) as stored:
            self.assertEqual(stored.format, 'WEBP')

    def test_large_image_is_resized(self):
        upload = SimpleUploadedFile('grande.jpg', build_image_bytes(size=(3000, 2000)), content_type='image/jpeg')
        image = ProductImage.objects.create(product=self.product, image=upload)
        self.assertLessEqual(max(image.width, image.height), 1200)
        self.assertGreater(image.size_bytes, 0)

    def test_rejects_non_image_upload(self):
        upload = SimpleUploadedFile('nota.txt', b'contenido plano', content_type='text/plain')
        with self.assertRaises(InvalidImageError):
            ProductImage.objects.create(product=self.product, image=upload)


class ProductApiTests(DomainTestCase):
    def test_creating_a_product_generates_a_code(self):
        self.as_user(self.manager)
        response = self.client.post(
            '/api/products/',
            {
                'name': 'Café molido 250g',
                'brand': 'Mayu',
                'unit_of_measure': 'UNIDAD',
                'units_per_package': 12,
                'cost_usd': '4.20',
                'price_usd': '6.00',
                'barcode': '  ',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data['code'].startswith('P'))
        self.assertIsNone(response.data['barcode'])
        self.assertEqual(response.data['stock'], '0.000')

    def test_product_creation_rejects_negative_amounts(self):
        self.as_user(self.manager)
        response = self.client.post(
            '/api/products/', {'name': 'X', 'price_usd': '-1.00'}, format='json'
        )
        self.assertEqual(response.status_code, 400)

    def test_stock_is_read_only_for_clients(self):
        self.as_user(self.manager)
        response = self.client.patch(
            f'/api/products/{self.product.pk}/', {'stock': '999'}, format='json'
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal('0.000'))

    def test_barcode_lookup(self):
        self.product.barcode = '7801234567890'
        self.product.save(update_fields=['barcode'])
        self.as_user(self.cashier)
        response = self.client.get('/api/products/barcode_lookup/', {'code': '7801234567890'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], self.product.pk)

    def test_barcode_lookup_not_found(self):
        self.as_user(self.cashier)
        response = self.client.get('/api/products/barcode_lookup/', {'code': '000'})
        self.assertEqual(response.status_code, 404)

    def test_list_is_paginated_and_searchable(self):
        self.as_user(self.cashier)
        response = self.client.get('/api/products/', {'search': 'Tostones'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('results', response.data)
        self.assertEqual(response.data['count'], 1)

    def test_endpoint_requires_authentication(self):
        response = self.client.get('/api/products/')
        self.assertEqual(response.status_code, 401)


class RolePermissionTests(DomainTestCase):
    def test_cashier_cannot_create_products(self):
        self.as_user(self.cashier)
        response = self.client.post('/api/products/', {'name': 'No permitido'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_warehouse_cannot_create_sales(self):
        self.as_user(self.warehouse)
        response = self.client.post('/api/sales/', {'items': []}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_cashier_cannot_read_the_exchange_rate(self):
        self.as_user(self.cashier)
        self.assertEqual(self.client.get('/api/rates/').status_code, 403)
        self.as_user(self.manager)
        self.assertEqual(self.client.get('/api/rates/').status_code, 200)

    def test_only_managers_and_admins_change_the_store_config(self):
        self.as_user(self.cashier)
        self.assertEqual(
            self.client.patch(
                '/api/core/config/store/1/', {'allow_zero_stock_sale': True}, format='json'
            ).status_code,
            403,
        )
        self.as_user(self.manager)
        self.assertEqual(
            self.client.patch(
                '/api/core/config/store/1/', {'allow_zero_stock_sale': True}, format='json'
            ).status_code,
            200,
        )
        self.assertTrue(StoreConfig.load().allow_zero_stock_sale)

    def test_inactive_user_is_rejected(self):
        self.cashier.is_active = False
        self.cashier.save(update_fields=['is_active'])
        self.as_user(self.cashier)
        self.assertEqual(self.client.get('/api/products/').status_code, 403)


class AuthApiTests(DomainTestCase):
    def test_login_returns_a_token_and_the_user_roles(self):
        response = self.client.post(
            '/api/core/auth/login/',
            {'username': 'cashier', 'password': 'testpass123'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn('token', response.data)
        self.assertIn('CAJERO', response.data['user']['roles'])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {response.data['token']}")
        me = self.client.get('/api/core/auth/me/')
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data['username'], 'cashier')

    def test_login_with_wrong_password_fails(self):
        response = self.client.post(
            '/api/core/auth/login/', {'username': 'cashier', 'password': 'nope'}, format='json'
        )
        self.assertEqual(response.status_code, 400)

    def test_logout_invalidates_the_token(self):
        response = self.client.post(
            '/api/core/auth/login/', {'username': 'cashier', 'password': 'testpass123'}, format='json'
        )
        token = response.data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        self.assertEqual(self.client.post('/api/core/auth/logout/').status_code, 204)
        self.assertEqual(self.client.get('/api/core/auth/me/').status_code, 401)


class InventoryApiTests(DomainTestCase):
    def test_entry_endpoint_creates_the_document_and_movements(self):
        self.as_user(self.warehouse)
        response = self.client.post(
            '/api/goods-entries/',
            {
                'entry_date': str(self.rate.effective_date),
                'currency': CURRENCY_USD,
                'supplier_name': 'Almacén del Centro',
                'items': [{'product_id': self.product.pk, 'quantity': '12', 'unit_cost': '2.00'}],
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['total_usd'], '24.00')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal('12.000'))
        self.assertEqual(GoodsEntry.objects.count(), 1)

    def test_entry_with_unknown_product_is_rejected(self):
        self.as_user(self.warehouse)
        response = self.client.post(
            '/api/goods-entries/',
            {
                'entry_date': str(self.rate.effective_date),
                'currency': CURRENCY_USD,
                'items': [{'product_id': 9999, 'quantity': '1', 'unit_cost': '1.00'}],
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_exit_note_endpoint(self):
        self.as_user(self.warehouse)
        self.client.post(
            '/api/goods-entries/',
            {
                'entry_date': str(self.rate.effective_date),
                'currency': CURRENCY_USD,
                'items': [{'product_id': self.product.pk, 'quantity': '8', 'unit_cost': '2.00'}],
            },
            format='json',
        )
        response = self.client.post(
            '/api/exit-notes/',
            {
                'reason': 'MERMA',
                'description': 'Producto mojado en el estante',
                'exit_date': str(self.rate.effective_date),
                'items': [{'product_id': self.product.pk, 'quantity': '3'}],
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal('5.000'))
        self.assertEqual(ExitNote.objects.count(), 1)

    def test_exit_note_beyond_stock_returns_400(self):
        self.as_user(self.warehouse)
        response = self.client.post(
            '/api/exit-notes/',
            {
                'reason': 'PERDIDA',
                'description': 'Pérdida total del producto',
                'exit_date': str(self.rate.effective_date),
                'items': [{'product_id': self.product.pk, 'quantity': '3'}],
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ExitNote.objects.count(), 0)

    def test_stock_movements_are_read_only(self):
        self.as_user(self.warehouse)
        self.assertEqual(self.client.post('/api/stock-movements/', {}, format='json').status_code, 403)


class SalesApiTests(DomainTestCase):
    def _stock_product(self, quantity='10'):
        self.as_user(self.warehouse)
        self.client.post(
            '/api/goods-entries/',
            {
                'entry_date': str(self.rate.effective_date),
                'currency': CURRENCY_USD,
                'items': [{'product_id': self.product.pk, 'quantity': quantity, 'unit_cost': '2.00'}],
            },
            format='json',
        )

    def test_paid_sale_endpoint(self):
        self._stock_product()
        self.as_user(self.cashier)
        response = self.client.post(
            '/api/sales/',
            {
                'sale_type': 'PAID',
                'currency': 'USD',
                'paid_amount': '7.00',
                'payment_method': 'CASH_USD',
                'items': [{'product_id': self.product.pk, 'quantity': '2'}],
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['total_usd'], '7.00')
        self.assertEqual(response.data['total_ves'], '255.50')
        self.assertEqual(response.data['exchange_rate_applied'], '36.5000')

    def test_credit_sale_endpoint_requires_customer(self):
        self._stock_product()
        self.as_user(self.cashier)
        response = self.client.post(
            '/api/sales/',
            {
                'sale_type': 'CREDIT',
                'items': [{'product_id': self.product.pk, 'quantity': '1'}],
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('customer_id', response.data)

    def test_credit_sale_endpoint_opens_a_debt(self):
        self._stock_product()
        customer = Customer.objects.create(document_id='V-99999999', name='José Pérez')
        self.as_user(self.cashier)
        response = self.client.post(
            '/api/sales/',
            {
                'sale_type': 'CREDIT',
                'customer_id': customer.pk,
                'items': [{'product_id': self.product.pk, 'quantity': '2'}],
            },
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['amount_due_usd'], '7.00')
        self.assertEqual(CustomerDebt.objects.get().balance_usd, Decimal('7.00'))

    def test_quote_endpoint_uses_current_rate_and_surcharge(self):
        StoreConfig.load()
        config = StoreConfig.load()
        config.default_surcharge_percentage = Decimal('20.00')
        config.save(update_fields=['default_surcharge_percentage'])
        self.as_user(self.cashier)

        response = self.client.post(
            '/api/sales/quote/',
            {'items': [{'product_id': self.product.pk, 'quantity': '2'}]},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['subtotal_usd'], '7.00')
        self.assertEqual(response.data['surcharge_usd'], '1.40')
        self.assertEqual(response.data['total_usd'], '8.40')
        self.assertEqual(response.data['exchange_rate_applied'], '36.5000')

    def test_payment_endpoint_uses_the_rate_of_the_day(self):
        self._stock_product()
        customer = Customer.objects.create(name='Cliente Abono')
        self.as_user(self.cashier)
        sale = self.client.post(
            '/api/sales/',
            {
                'sale_type': 'CREDIT',
                'customer_id': customer.pk,
                'items': [{'product_id': self.product.pk, 'quantity': '2'}],
            },
            format='json',
        )
        debt_id = sale.data['id']
        debt = CustomerDebt.objects.get(sale_id=debt_id)

        self.change_rate(Decimal('40.0000'))
        response = self.client.post(
            f'/api/debts/{debt.pk}/payments/',
            {'amount': '140.00', 'currency': 'VES', 'method': 'CASH_VES'},
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['amount_usd'], '3.50')
        self.assertEqual(response.data['debt']['balance_usd'], '3.50')
        self.assertEqual(response.data['debt']['status'], 'OPEN')

    def test_payment_endpoint_rejects_wrong_currency_method_pair(self):
        self._stock_product()
        customer = Customer.objects.create(name='Cliente Abono 2')
        self.as_user(self.cashier)
        self.client.post(
            '/api/sales/',
            {
                'sale_type': 'CREDIT',
                'customer_id': customer.pk,
                'items': [{'product_id': self.product.pk, 'quantity': '1'}],
            },
            format='json',
        )
        debt = CustomerDebt.objects.get()
        response = self.client.post(
            f'/api/debts/{debt.pk}/payments/',
            {'amount': '10.00', 'currency': 'VES', 'method': 'CASH_USD'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_void_sale_endpoint_restores_stock(self):
        self._stock_product()
        self.as_user(self.cashier)
        sale = self.client.post(
            '/api/sales/',
            {
                'sale_type': 'PAID',
                'paid_amount': '3.50',
                'items': [{'product_id': self.product.pk, 'quantity': '1'}],
            },
            format='json',
        )
        response = self.client.post(
            f"/api/sales/{sale.data['id']}/void/",
            {'reason': 'Se cobró el producto equivocado'},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['status'], 'ANULLED')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, Decimal('10.000'))

    def test_summary_endpoint(self):
        self._stock_product()
        self.as_user(self.cashier)
        self.client.post(
            '/api/sales/',
            {
                'sale_type': 'PAID',
                'paid_amount': '3.50',
                'items': [{'product_id': self.product.pk, 'quantity': '1'}],
            },
            format='json',
        )
        response = self.client.get('/api/sales-summary/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['sales_count'], 1)
        self.assertEqual(response.data['total_usd'], '3.50')
        self.assertEqual(response.data['pending_debt_usd'], '0.00')

    def test_customer_balance_is_reported(self):
        self._stock_product()
        customer = Customer.objects.create(name='Deudor Test')
        self.as_user(self.cashier)
        self.client.post(
            '/api/sales/',
            {
                'sale_type': 'CREDIT',
                'customer_id': customer.pk,
                'items': [{'product_id': self.product.pk, 'quantity': '2'}],
            },
            format='json',
        )
        response = self.client.get('/api/customers/', {'search': 'Deudor Test'})
        self.assertEqual(response.data['results'][0]['balance_usd'], '7.00')
        self.assertEqual(response.data['results'][0]['open_debts'], 1)


class RateApiTests(DomainTestCase):
    def test_manual_rate_requires_a_reason(self):
        self.as_user(self.manager)
        response = self.client.post(
            '/api/rates/manual/', {'rate': '38.0000', 'effective_date': '2026-01-01', 'notes': ''}, format='json'
        )
        self.assertEqual(response.status_code, 400)

    def test_manual_rate_does_not_touch_the_official_row(self):
        self.as_user(self.manager)
        official_before = self.rate.rate
        response = self.client.post(
            '/api/rates/manual/',
            {'rate': '38.0000', 'effective_date': '2026-01-01', 'notes': 'BCV no disponible'},
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.rate.refresh_from_db()
        self.assertEqual(self.rate.rate, official_before)
        self.assertEqual(response.data['source'], 'MANUAL')

    def test_current_endpoint(self):
        self.as_user(self.cashier)
        self.assertEqual(self.client.get('/api/rates/current/').status_code, 403)
        self.as_user(self.manager)
        response = self.client.get('/api/rates/current/')
        self.assertEqual(response.data['rate'], '36.5000')


class StoreConfigTests(DomainTestCase):
    def test_config_is_a_singleton(self):
        first = StoreConfig.load()
        second = StoreConfig.load()
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(StoreConfig.objects.count(), 1)
        self.assertEqual(StoreConfig.objects.filter(pk=1).count(), 1)

    def test_singleton_is_guarded_by_a_database_constraint(self):
        constraint_names = {c.name for c in StoreConfig._meta.constraints}
        self.assertIn('store_config_singleton_pk_1', constraint_names)

    def test_config_cannot_be_deleted(self):
        with self.assertRaises(ValueError):
            StoreConfig.load().delete()

    def test_surcharge_percentage_rejects_negatives(self):
        config = StoreConfig(default_surcharge_percentage=Decimal('-1.00'))
        with self.assertRaises(ValidationError):
            config.full_clean()
