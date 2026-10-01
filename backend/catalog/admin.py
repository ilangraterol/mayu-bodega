from django.contrib import admin
from django.utils.html import format_html

from catalog.models import Category, Product, ProductImage


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    readonly_fields = ['preview', 'width', 'height', 'size_bytes']
    fields = ['preview', 'image', 'is_primary', 'sort_order', 'width', 'height', 'size_bytes']

    def preview(self, obj):
        if not obj.thumbnail:
            return '-'
        return format_html('<img src="{}" style="max-height:80px;border-radius:6px" />', obj.thumbnail.url)

    preview.short_description = 'Vista previa'


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'surcharge_percentage', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code']
    readonly_fields = ['code', 'created_at', 'updated_at']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'code',
        'name',
        'brand',
        'category',
        'surcharge_percentage',
        'unit_of_measure',
        'stock',
        'cost_usd',
        'price_usd',
        'is_active',
    ]
    list_filter = ['is_active', 'unit_of_measure', 'brand', 'category']
    search_fields = ['name', 'code', 'barcode', 'brand']
    list_select_related = ['category']
    readonly_fields = ['code', 'stock', 'created_at', 'updated_at']
    inlines = [ProductImageInline]


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['id', 'product', 'is_primary', 'sort_order', 'created_at']
    list_filter = ['is_primary']
    search_fields = ['product__name', 'product__code']
