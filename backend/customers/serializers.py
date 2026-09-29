from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers

from core.money import MONEY_PLACES
from customers.models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    balance_usd = serializers.SerializerMethodField()
    open_debts = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id',
            'document_id',
            'name',
            'phone',
            'address',
            'notes',
            'is_active',
            'balance_usd',
            'open_debts',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['balance_usd', 'open_debts', 'created_at', 'updated_at']

    def get_balance_usd(self, obj) -> str:
        total = (
            obj.debts.exclude(status__in=['PAID', 'ANULLED'])
            .aggregate(total=Sum('balance_usd'))['total']
        )
        return f'{Decimal(total or 0):.{MONEY_PLACES}f}'

    def get_open_debts(self, obj) -> int:
        return obj.debts.exclude(status__in=['PAID', 'ANULLED']).count()

    def validate_document_id(self, value):
        return (value or '').strip() or None

    def validate_name(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('El nombre del cliente es obligatorio.')
        return value
