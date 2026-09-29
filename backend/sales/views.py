from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from catalog.models import Product
from core.money import quantize_money, usd_to_ves
from core.models import StoreConfig
from core.permissions import CanAccessResource
from customers.models import Customer
from rates.models import ExchangeRate
from sales import services
from sales.models import CustomerDebt, DebtPayment, DebtStatus, Sale, SaleStatus, SaleType
from sales.serializers import (
    CustomerDebtSerializer,
    DebtPaymentCreateSerializer,
    DebtPaymentSerializer,
    QuoteSerializer,
    SaleCreateSerializer,
    SaleSerializer,
    VoidSerializer,
)


def _build_lines(raw_items: list[dict]) -> list[dict]:
    """Resolve catalogue prices for the lines that do not carry an explicit price."""
    lines = []
    for raw in raw_items:
        product = Product.objects.filter(pk=raw['product_id']).first()
        if product is None:
            raise services.ValidationError('Artículo no encontrado.')
        unit_price = raw.get('unit_price_usd')
        lines.append(
            {
                'product_id': product.pk,
                'quantity': raw['quantity'],
                'unit_price_usd': product.price_usd if unit_price is None else unit_price,
            }
        )
    return lines


class SaleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Sale.objects.select_related('customer', 'created_by').prefetch_related('items__product')
    serializer_class = SaleSerializer
    permission_model = Sale
    permission_classes = [CanAccessResource]
    action_permissions = {'quote': 'sales.view_sale', 'void': 'sales.change_sale'}
    filterset_fields = ['sale_type', 'status', 'currency', 'sale_date', 'customer']
    search_fields = ['code', 'customer__name', 'notes']
    ordering_fields = ['sale_date', 'created_at', 'total_usd']

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get('today') == 'true':
            queryset = queryset.filter(sale_date=timezone.localdate())
        return queryset

    def create(self, request):
        serializer = SaleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)

        customer = None
        if data.get('customer_id'):
            customer = Customer.objects.filter(pk=data['customer_id']).first()
            if customer is None:
                return Response(
                    {'customer_id': ['Cliente no encontrado.']}, status=status.HTTP_400_BAD_REQUEST
                )

        sale = services.create_sale(
            user=request.user,
            items=_build_lines(data['items']),
            sale_type=data['sale_type'],
            sale_date=data.get('sale_date'),
            customer=customer,
            currency=data['currency'],
            paid_amount=data.get('paid_amount'),
            payment_method=data['payment_method'],
            notes=data.get('notes', ''),
        )
        sale = self.get_queryset().get(pk=sale.pk)
        return Response(self.get_serializer(sale).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def void(self, request, pk=None):
        sale = self.get_object()
        serializer = VoidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.void_sale(user=request.user, sale=sale, reason=serializer.validated_data['reason'])
        sale.refresh_from_db()
        return Response(self.get_serializer(sale).data)

    @action(detail=False, methods=['post'], url_path='quote')
    def quote(self, request):
        """Preview cart totals with the current rate and the configured surcharge."""
        serializer = QuoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        rate = ExchangeRate.get_current()
        if rate is None:
            return Response(
                {'detail': 'No hay tasa de cambio registrada todavía.'},
                status=status.HTTP_409_CONFLICT,
            )

        config = StoreConfig.load()
        lines = []
        for raw in serializer.validated_data['items']:
            product = Product.objects.filter(pk=raw['product_id']).first()
            if product is None:
                return Response({'detail': 'Artículo no encontrado.'}, status=status.HTTP_400_BAD_REQUEST)
            unit_price = product.price_usd if raw.get('unit_price_usd') is None else raw['unit_price_usd']
            lines.append(
                {
                    'product_id': product.pk,
                    'product_code': product.code,
                    'product_name': product.name,
                    'quantity': raw['quantity'],
                    'unit_price_usd': unit_price,
                    'stock': product.stock,
                    'line_total_usd': quantize_money(raw['quantity'] * unit_price),
                }
            )

        totals = services.compute_totals(lines, config.default_surcharge_percentage)
        return Response(
            {
                'subtotal_usd': str(totals['subtotal_usd']),
                'surcharge_usd': str(totals['surcharge_usd']),
                'total_usd': str(totals['total_usd']),
                'total_ves': str(usd_to_ves(totals['total_usd'], rate.rate)),
                'exchange_rate_applied': str(rate.rate),
                'rate_effective_date': rate.effective_date,
                'surcharge_percentage': str(config.default_surcharge_percentage),
                'allow_zero_stock_sale': config.allow_zero_stock_sale,
                'lines': [
                    {
                        **line,
                        # Every decimal travels as a string: the client must never
                        # parse money or quantities as floats.
                        'stock': str(line['stock']),
                        'quantity': str(line['quantity']),
                        'unit_price_usd': str(line['unit_price_usd']),
                        'line_total_usd': str(line['line_total_usd']),
                    }
                    for line in lines
                ],
            }
        )


class CustomerDebtViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CustomerDebt.objects.select_related('customer', 'sale').prefetch_related('payments')
    serializer_class = CustomerDebtSerializer
    permission_model = CustomerDebt
    permission_classes = [CanAccessResource]
    action_permissions = {'add_payment': 'sales.add_debtpayment'}
    filterset_fields = ['status', 'customer']
    search_fields = ['customer__name', 'customer__document_id', 'sale__code']
    ordering_fields = ['created_at', 'balance_usd', 'sale__sale_date']

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.query_params.get('open_only') == 'true':
            queryset = queryset.filter(status=DebtStatus.OPEN)
        return queryset

    @action(detail=True, methods=['post'], url_path='payments')
    def add_payment(self, request, pk=None):
        debt = self.get_object()
        serializer = DebtPaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = services.register_payment(user=request.user, debt=debt, **serializer.validated_data)
        debt.refresh_from_db()
        payload = DebtPaymentSerializer(payment).data
        payload['debt'] = CustomerDebtSerializer(debt).data
        return Response(payload, status=status.HTTP_201_CREATED)


class DebtPaymentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DebtPayment.objects.select_related('debt', 'recorded_by')
    serializer_class = DebtPaymentSerializer
    permission_model = DebtPayment
    permission_classes = [CanAccessResource]
    action_permissions = {'void': 'sales.change_debtpayment'}
    filterset_fields = ['debt', 'currency', 'method', 'is_voided']
    ordering_fields = ['paid_at', 'created_at', 'amount_usd']

    @action(detail=True, methods=['post'])
    def void(self, request, pk=None):
        payment = self.get_object()
        serializer = VoidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.void_payment(user=request.user, payment=payment, reason=serializer.validated_data['reason'])
        payment.refresh_from_db()
        return Response(self.get_serializer(payment).data)


class SalesSummaryViewSet(viewsets.ViewSet):
    """Cash register summary: today's sales plus the pending credit balance."""

    permission_model = Sale
    permission_classes = [CanAccessResource]

    def list(self, request):
        today = timezone.localdate()
        sales = Sale.objects.filter(sale_date=today, status=SaleStatus.COMPLETED)
        open_debts = CustomerDebt.objects.filter(status=DebtStatus.OPEN)
        return Response(
            {
                'date': today,
                'sales_count': sales.count(),
                'total_usd': str(
                    quantize_money(sales.aggregate(total=Sum('total_usd'))['total'] or Decimal('0.00'))
                ),
                'credit_sales_count': sales.filter(sale_type=SaleType.CREDIT).count(),
                'open_debts_count': open_debts.count(),
                'pending_debt_usd': str(
                    quantize_money(open_debts.aggregate(total=Sum('balance_usd'))['total'] or Decimal('0.00'))
                ),
            }
        )
