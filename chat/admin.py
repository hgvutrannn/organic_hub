from django.contrib import admin
from .models import Message

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('message_id', 'sender', 'recipient', 'content_preview', 'room_name', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at', 'room_name')
    search_fields = ('sender__full_name', 'recipient__full_name', 'content', 'room_name')
    readonly_fields = ('message_id', 'created_at')
    list_per_page = 25
    
    def content_preview(self, obj):
        """Display message content preview"""
        if len(obj.content) > 50:
            return obj.content[:50] + "..."
        return obj.content
    content_preview.short_description = "Content"
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('message_id', 'sender', 'recipient', 'room_name')
        }),
        ('Message Content', {
            'fields': ('content',)
        }),
        ('Status', {
            'fields': ('is_read', 'created_at')
        }),
    )
    
    def get_queryset(self, request):
        """Optimize query to avoid N+1 problem"""
        return super().get_queryset(request).select_related('sender', 'recipient')
