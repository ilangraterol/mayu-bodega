from django.contrib import admin

from rates.models import ExchangeRate


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ['rate', 'effective_date', 'source', 'is_active', 'fetched_at', 'recorded_by']
    list_filter = ['source', 'is_active']
    search_fields = ['rate', 'effective_date']
    readonly_fields = ['fetched_at', 'recorded_by']
