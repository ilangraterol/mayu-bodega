from decimal import Decimal

from rest_framework import serializers

from catalog.surcharge import SURCHARGE_MAX_PERCENT
from core.enums import CURRENCY_CHOICES, CURRENCY_USD
from core.money import MONEY_PLACES, QUANTITY_PLACES
from customers.models import Customer
from sales.models import (
    CustomerDebt,
    DebtPayment,
    PaymentMethod,
    Sale,
    SaleItem,
    SaleType,
)


class SaleItemSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    primary_image_url = serializers.SerializerMethodField()
    surcharge_source_display = serializers.CharField(source='get_surcharge_source_display', read_only=True)

    class Meta:
        model = SaleItem
        fields = [
            'id',
            'product',
            'product_code',
            'product_name',
            'primary_image_url',
            'quantity',
            'unit_price_usd',
            'line_total_usd',
            'surcharge_percentage',
            'surcharge_usd',
            'surcharge_source',
            'surcharge_source_display',
        ]
        read_only_fields = ['line_total_usd']

    def get_primary_image_url(self, obj) -> str:
        image = obj.product.primary_image
        if not image:
            return ''
        field = image.thumbnail or image.image
        if not field:
            return ''
        request = self.context.get('request')
        return request.build_absolute_uri(field.url) if request else field.url


class DebtPaymentSerializer(serializers.ModelSerializer):
    recorded_by = serializers.CharField(source='recorded_by.username', read_only=True)

    class Meta:
        model = DebtPayment
        fields = [
            'id',
            'debt',
            'currency',
            'amount',
            'exchange_rate_applied',
            'amount_usd',
            'method',
            'paid_at',
            'is_voided',
            'voided_at',
            'void_reason',
            'notes',
            'recorded_by',
            'created_at',
        ]
        read_only_fields = [
            'debt',
            'currency',
            'amount',
            'exchange_rate_applied',
            'amount_usd',
            'method',
            'paid_at',
            'is_voided',
            'voided_at',
            'void_reason',
            'recorded_by',
            'created_at',
        ]


class CustomerDebtSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_document_id = serializers.CharField(source='customer.document_id', read_only=True)
    sale_code = serializers.CharField(source='sale.code', read_only=True)
    sale_date = serializers.DateField(source='sale.sale_date', read_only=True)
    payments = DebtPaymentSerializer(many=True, read_only=True)

    class Meta:
        model = CustomerDebt
        fields = [
            'id',
            'sale',
            'sale_code',
            'sale_date',
            'customer',
            'customer_name',
            'customer_document_id',
            'original_amount_usd',
            'paid_amount_usd',
            'balance_usd',
            'status',
            'payments',
            'created_at',
            'updated_at',
        ]


class SaleSerializer(serializers.ModelSerializer):
    sale_type_display = serializers.CharField(source='get_sale_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True, default=None)
    items = SaleItemSerializer(many=True, read_only=True)
    created_by = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id',
            'code',
            'sale_type',
            'sale_type_display',
            'customer',
            'customer_name',
            'sale_date',
            'currency',
            'exchange_rate_applied',
            'surcharge_percentage',
            'subtotal_usd',
            'surcharge_usd',
            'total_usd',
            'total_ves',
            'paid_amount',
            'payment_method',
            'amount_due_usd',
            'status',
            'status_display',
            'void_reason',
            'voided_at',
            'notes',
            'created_by',
            'created_at',
            'items',
        ]


class SaleItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=QUANTITY_PLACES, min_value=Decimal('0.001'))
    unit_price_usd = serializers.DecimalField(
        max_digits=12, decimal_places=MONEY_PLACES, required=False, min_value=Decimal('0.00')
    )
    # The percentage the cashier chose for this line. Omitted means "use the
    # catalogue", which is what an untouched cart sends.
    surcharge_percentage = serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        required=False,
        allow_null=True,
        min_value=Decimal('0.00'),
        max_value=SURCHARGE_MAX_PERCENT,
    )


class SaleCreateSerializer(serializers.Serializer):
    sale_type = serializers.ChoiceField(choices=SaleType.choices, default=SaleType.PAID)
    customer_id = serializers.IntegerField(required=False, allow_null=True)
    sale_date = serializers.DateField(required=False, allow_null=True)
    currency = serializers.ChoiceField(choices=CURRENCY_CHOICES, default=CURRENCY_USD)
    paid_amount = serializers.DecimalField(
        max_digits=16, decimal_places=MONEY_PLACES, required=False, allow_null=True, min_value=Decimal('0.00')
    )
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices, default=PaymentMethod.CASH_USD)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    items = SaleItemInputSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        if attrs['sale_type'] == SaleType.CREDIT and not attrs.get('customer_id'):
            raise serializers.ValidationError(
                {'customer_id': 'Una venta fiada requiere un cliente.'}
            )
        if attrs['sale_type'] == SaleType.PAID and attrs.get('paid_amount') is None:
            raise serializers.ValidationError(
                {'paid_amount': 'Indique el monto pagado en una venta pagada.'}
            )
        return attrs


class DebtPaymentCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=16, decimal_places=MONEY_PLACES, min_value=Decimal('0.01'))
    currency = serializers.ChoiceField(choices=CURRENCY_CHOICES)
    method = serializers.ChoiceField(choices=PaymentMethod.choices)
    paid_at = serializers.DateTimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        currency = attrs['currency']
        method = attrs['method']
        if currency == 'USD' and method == 'CASH_VES':
            raise serializers.ValidationError(
                {'method': 'Use CASH_USD para un abono en dólares.'}
            )
        if currency == 'VES' and method == 'CASH_USD':
            raise serializers.ValidationError(
                {'method': 'Use CASH_VES para un abono en bolívares.'}
            )
        return attrs


class VoidSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=5)


class QuoteSerializer(serializers.Serializer):
    """Read only preview of a cart: totals with the current rate and surcharge."""

    items = SaleItemInputSerializer(many=True, allow_empty=False)

    def validate_items(self, value):
        seen = set()
        for line in value:
            if line['product_id'] in seen:
                raise serializers.ValidationError('No repita el mismo producto en dos líneas.')
            seen.add(line['product_id'])
        return value
