from django.contrib import admin
from .models import UserProductView


@admin.register(UserProductView)
class UserProductViewAdmin(admin.ModelAdmin):
    list_display = ('view_id', 'user', 'session_key', 'product', 'view_count', 'viewed_at')
    list_filter = ('viewed_at',)
    search_fields = ('user__email', 'user__full_name', 'product__name', 'session_key')
    readonly_fields = ('viewed_at',)
    date_hierarchy = 'viewed_at'
    
    fieldsets = (
        ('Thông tin người dùng', {
            'fields': ('user', 'session_key')
        }),
        ('Thông tin sản phẩm', {
            'fields': ('product', 'view_count', 'viewed_at')
        }),
    )
