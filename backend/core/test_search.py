"""Regression tests for accent insensitive search.

Typing ``azu`` must find ``Azúcar``. DRF's ``SearchFilter`` is case insensitive
but accent sensitive, and SQLite has no ``unaccent``, so ``core.search``
registers the function on each connection and the whole catalogue, customers,
sales and inventory lists depend on it.
"""

from decimal import Decimal

from catalog.models import Product
from core.search import MIN_UNACCENT_LENGTH, strip_accents
from core.testing import DomainTestCase
from customers.models import Customer


class StripAccentsTestCase(DomainTestCase):
    def test_folds_the_spanish_accents(self):
        self.assertEqual(strip_accents('Azúcar'), 'azucar')
        self.assertEqual(strip_accents('ATÚN'), 'atun')
        self.assertEqual(strip_accents('Café molido'), 'cafe molido')
        self.assertEqual(strip_accents('limón'), 'limon')

    def test_folds_enye_so_both_spellings_match(self):
        # ñ normalises to n, so "ano" also has to find "año".
        self.assertEqual(strip_accents('Año'), 'ano')
        self.assertEqual(strip_accents('ANO'), 'ano')

    def test_handles_none_and_empty(self):
        self.assertEqual(strip_accents(None), '')
        self.assertEqual(strip_accents(''), '')


class ProductSearchTestCase(DomainTestCase):
    def setUp(self):
        super().setUp()
        self.as_user(self.admin)
        Product.objects.create(
            name='Azúcar 1kg',
            brand='Mayu',
            cost_usd=Decimal('1.00'),
            price_usd=Decimal('1.20'),
        )
        Product.objects.create(
            name='Atún en lata 170g',
            brand='Mar',
            cost_usd=Decimal('2.00'),
            price_usd=Decimal('2.40'),
        )
        Product.objects.create(
            name='Café molido 500g',
            brand='Mayu',
            cost_usd=Decimal('4.00'),
            price_usd=Decimal('5.20'),
        )

    def search(self, term):
        response = self.client.get('/api/products/', {'search': term})
        self.assertEqual(response.status_code, 200, response.data)
        return {row['name'] for row in response.data['results']}

    def test_partial_word_without_accents_finds_the_accented_name(self):
        self.assertIn('Azúcar 1kg', self.search('azu'))

    def test_full_word_matches_with_or_without_accents(self):
        for term in ('azucar', 'AZUCAR', 'Azúcar', 'AZÚCAR'):
            with self.subTest(term=term):
                self.assertIn('Azúcar 1kg', self.search(term))

    def test_matches_atun_and_cafe_without_accents(self):
        self.assertIn('Atún en lata 170g', self.search('atun'))
        self.assertIn('Café molido 500g', self.search('cafe'))

    def test_matches_on_the_brand_too(self):
        self.assertIn('Atún en lata 170g', self.search('mar'))

    def test_single_letter_search_does_not_explode(self):
        """A needle that folds to one character would match nearly every row.

        "ñ" normalises to "n", which is why ``MIN_UNACCENT_LENGTH`` keeps the
        original accented term instead of broadening the match.
        """
        Product.objects.create(
            name='Caña de azúcar 1L',
            brand='Mayu',
            cost_usd=Decimal('1.50'),
            price_usd=Decimal('2.00'),
        )

        # The accented term is matched literally, not as "n".
        self.assertEqual(self.search('ñ'), {'Caña de azúcar 1L'})
        # And it does not drag in the rest of the catalogue.
        self.assertNotIn('Azúcar 1kg', self.search('ñ'))

    def test_enye_search_is_not_broken(self):
        Product.objects.create(
            name='Caña de azúcar 1L',
            brand='Mayu',
            cost_usd=Decimal('1.50'),
            price_usd=Decimal('2.00'),
        )
        # Both spellings resolve: "canya" folds through unaccent, "caña" too.
        self.assertIn('Caña de azúcar 1L', self.search('cana'))
        self.assertIn('Caña de azúcar 1L', self.search('aña'))

    def test_minimum_length_guard_is_two(self):
        self.assertEqual(MIN_UNACCENT_LENGTH, 2)

    def test_no_results_for_an_unrelated_term(self):
        self.assertEqual(self.search('llavero'), set())

    def test_search_by_code_still_works(self):
        code = Product.objects.get(name='Azúcar 1kg').code
        self.assertIn('Azúcar 1kg', self.search(code))

    def test_empty_search_returns_the_whole_catalogue(self):
        self.assertEqual(len(self.search('   ')), Product.objects.count())


class RelatedSearchTestCase(DomainTestCase):
    def setUp(self):
        super().setUp()
        self.as_user(self.admin)
        self.customer = Customer.objects.create(
            document_id='V-12345678', name='María González'
        )

    def test_customer_search_ignores_accents(self):
        for term in ('maria', 'MARIA', 'María', 'gonzalez', 'GONZALEZ'):
            with self.subTest(term=term):
                response = self.client.get('/api/customers/', {'search': term})
                self.assertEqual(response.status_code, 200, response.data)
                codes = [row['document_id'] for row in response.data['results']]
                self.assertIn(self.customer.document_id, codes)

    def test_related_lookup_search_does_not_break(self):
        """`search_fields` entries like `customer__name` must still resolve."""
        response = self.client.get('/api/debts/', {'search': 'maria'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('count', response.data)

    def test_stock_movement_related_lookup_search_does_not_break(self):
        response = self.client.get('/api/stock-movements/', {'search': 'tostones'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('count', response.data)
