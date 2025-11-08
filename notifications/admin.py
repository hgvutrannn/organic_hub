from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'recipient', 'category', 'severity', 'order', 'is_read', 'created_at')
    list_filter = ('category', 'severity', 'is_read', 'created_at')
    search_fields = ('recipient__phone_number', 'recipient__email', 'message')
    autocomplete_fields = ('recipient', 'order')
