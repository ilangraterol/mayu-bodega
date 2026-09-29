from django.contrib import admin

from inventory.models import ExitNote, ExitNoteItem, GoodsEntry, GoodsEntryItem, StockMovement


class GoodsEntryItemInline(admin.TabularInline):
    model = GoodsEntryItem
    extra = 0
    readonly_fields = ['currency', 'rate_applied', 'unit_cost_usd', 'line_total_usd']


@admin.register(GoodsEntry)
class GoodsEntryAdmin(admin.ModelAdmin):
    list_display = ['code', 'entry_date', 'supplier_name', 'currency', 'total_usd', 'is_cancelled', 'created_by']
    list_filter = ['is_cancelled', 'currency']
    search_fields = ['code', 'supplier_name']
    readonly_fields = ['code', 'total_usd', 'created_by', 'created_at', 'cancelled_at']
    inlines = [GoodsEntryItemInline]


class ExitNoteItemInline(admin.TabularInline):
    model = ExitNoteItem
    extra = 0
    readonly_fields = ['unit_cost_usd']


@admin.register(ExitNote)
class ExitNoteAdmin(admin.ModelAdmin):
    list_display = ['code', 'exit_date', 'reason', 'total_units', 'is_cancelled', 'created_by']
    list_filter = ['is_cancelled', 'reason']
    search_fields = ['code', 'description']
    readonly_fields = ['code', 'total_units', 'created_by', 'created_at', 'cancelled_at']
    inlines = [ExitNoteItemInline]


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ['id', 'product', 'movement_type', 'origin', 'origin_id', 'quantity', 'balance_after', 'occurred_at']
    list_filter = ['movement_type', 'origin']
    search_fields = ['product__name', 'product__code', 'notes']
    readonly_fields = [f.name for f in StockMovement._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
