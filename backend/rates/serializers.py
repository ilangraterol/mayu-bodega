from decimal import Decimal

from rest_framework import serializers

from rates.models import ExchangeRate


class ExchangeRateSerializer(serializers.ModelSerializer):
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    recorded_by = serializers.CharField(source='recorded_by.username', read_only=True, default=None)

    class Meta:
        model = ExchangeRate
        fields = [
            'id',
            'rate',
            'effective_date',
            'fetched_at',
            'source',
            'source_display',
            'is_active',
            'recorded_by',
            'notes',
        ]
        read_only_fields = ['rate', 'effective_date', 'fetched_at', 'source', 'is_active', 'recorded_by']

    def validate_rate(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError('La tasa debe ser mayor que cero.')
        return value

    def validate(self, attrs):
        notes = attrs.get('notes', '')
        if not notes.strip():
            raise serializers.ValidationError(
                {'notes': 'Explique por qué registra una tasa manual.'}
            )
        return attrs


class ManualExchangeRateSerializer(serializers.Serializer):
    """Payload for the administrator's fallback rate."""

    rate = serializers.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal('0.0001'))
    effective_date = serializers.DateField()
    notes = serializers.CharField()

    def validate_rate(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError('La tasa debe ser mayor que cero.')
        return value

    def validate_notes(self, value):
        if len((value or '').strip()) < 5:
            raise serializers.ValidationError(
                'Explique por qué registra una tasa manual (mínimo 5 caracteres).'
            )
        return value
