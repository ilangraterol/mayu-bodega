from django.contrib import admin

from customers.models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['name', 'document_id', 'phone', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'document_id', 'phone']
    readonly_fields = ['created_at', 'updated_at']
