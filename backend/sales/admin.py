from django.contrib import admin

from sales.models import CustomerDebt, DebtPayment, Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ['line_total_usd', 'unit_cost_usd']


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['code', 'sale_date', 'sale_type', 'customer', 'total_usd', 'status', 'created_by']
    list_filter = ['sale_type', 'status', 'currency']
    search_fields = ['code', 'customer__name']
    readonly_fields = [
        'code',
        'exchange_rate_applied',
        'surcharge_percentage',
        'subtotal_usd',
        'surcharge_usd',
        'total_usd',
        'total_ves',
        'amount_due_usd',
        'status',
        'void_reason',
        'voided_at',
        'created_by',
        'created_at',
    ]
    inlines = [SaleItemInline]


@admin.register(CustomerDebt)
class CustomerDebtAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'sale', 'original_amount_usd', 'paid_amount_usd', 'balance_usd', 'status']
    list_filter = ['status']
    search_fields = ['customer__name', 'sale__code']
    readonly_fields = ['original_amount_usd', 'paid_amount_usd', 'balance_usd', 'status', 'created_at', 'updated_at']


@admin.register(DebtPayment)
class DebtPaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'debt', 'amount', 'currency', 'amount_usd', 'exchange_rate_applied', 'is_voided']
    list_filter = ['currency', 'method', 'is_voided']
    readonly_fields = [f.name for f in DebtPayment._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
