from decimal import Decimal

from rest_framework import serializers

from core.enums import CURRENCY_CHOICES, CURRENCY_USD
from core.money import MONEY_PLACES, QUANTITY_PLACES
from inventory.models import (
    ExitNote,
    ExitNoteItem,
    ExitNoteReason,
    GoodsEntry,
    GoodsEntryItem,
    StockMovement,
)


class StockMovementSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    movement_type_display = serializers.CharField(source='get_movement_type_display', read_only=True)
    origin_display = serializers.CharField(source='get_origin_display', read_only=True)
    created_by = serializers.CharField(source='created_by.username', read_only=True, default=None)

    class Meta:
        model = StockMovement
        fields = [
            'id',
            'product',
            'product_code',
            'product_name',
            'movement_type',
            'movement_type_display',
            'origin',
            'origin_display',
            'origin_id',
            'quantity',
            'unit_cost_usd',
            'unit_price_usd',
            'balance_after',
            'pending_after',
            'occurred_at',
            'notes',
            'created_by',
            'created_at',
        ]


class GoodsEntryItemSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = GoodsEntryItem
        fields = [
            'id',
            'product',
            'product_code',
            'product_name',
            'quantity',
            'unit_cost',
            'currency',
            'rate_applied',
            'unit_cost_usd',
            'line_total_usd',
        ]
        read_only_fields = ['currency', 'rate_applied', 'unit_cost_usd', 'line_total_usd']


class GoodsEntryItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=QUANTITY_PLACES, min_value=Decimal('0.001'))
    unit_cost = serializers.DecimalField(max_digits=12, decimal_places=MONEY_PLACES, min_value=Decimal('0.01'))


class GoodsEntrySerializer(serializers.ModelSerializer):
    items = GoodsEntryItemSerializer(many=True, read_only=True)
    created_by = serializers.CharField(source='created_by.username', read_only=True)
    supplier_name = serializers.CharField(required=False, allow_blank=True, default='')

    class Meta:
        model = GoodsEntry
        fields = [
            'id',
            'code',
            'supplier_name',
            'entry_date',
            'currency',
            'rate_applied',
            'total_usd',
            'notes',
            'is_cancelled',
            'cancelled_at',
            'created_by',
            'created_at',
            'items',
        ]
        read_only_fields = ['code', 'total_usd', 'is_cancelled', 'cancelled_at', 'created_by', 'created_at']

    def validate_currency(self, value):
        allowed = {code for code, _ in CURRENCY_CHOICES}
        if value not in allowed:
            raise serializers.ValidationError('Moneda no soportada.')
        return value


class GoodsEntryCreateSerializer(serializers.Serializer):
    supplier_name = serializers.CharField(required=False, allow_blank=True, default='')
    entry_date = serializers.DateField()
    currency = serializers.ChoiceField(choices=CURRENCY_CHOICES, default=CURRENCY_USD)
    rate_applied = serializers.DecimalField(
        max_digits=14, decimal_places=4, required=False, allow_null=True, min_value=Decimal('0.0001')
    )
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    items = GoodsEntryItemInputSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        if attrs.get('currency') == 'VES' and not attrs.get('rate_applied'):
            attrs['rate_applied'] = None  # resolved by the service from the current BCV rate
        return attrs


class ExitNoteItemSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = ExitNoteItem
        fields = ['id', 'product', 'product_code', 'product_name', 'quantity', 'unit_cost_usd']
        read_only_fields = ['unit_cost_usd']


class ExitNoteItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=QUANTITY_PLACES, min_value=Decimal('0.001'))


class ExitNoteSerializer(serializers.ModelSerializer):
    items = ExitNoteItemSerializer(many=True, read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    created_by = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = ExitNote
        fields = [
            'id',
            'code',
            'reason',
            'reason_display',
            'description',
            'exit_date',
            'total_units',
            'is_cancelled',
            'cancelled_at',
            'created_by',
            'created_at',
            'items',
        ]
        read_only_fields = ['code', 'total_units', 'is_cancelled', 'cancelled_at', 'created_by', 'created_at']


class ExitNoteCreateSerializer(serializers.Serializer):
    reason = serializers.ChoiceField(choices=ExitNoteReason.choices)
    description = serializers.CharField()
    exit_date = serializers.DateField()
    items = ExitNoteItemInputSerializer(many=True, allow_empty=False)

    def validate_description(self, value):
        value = (value or '').strip()
        if len(value) < 5:
            raise serializers.ValidationError('Describa el motivo con más detalle (mínimo 5 caracteres).')
        return value


class CancelDocumentSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=5)
