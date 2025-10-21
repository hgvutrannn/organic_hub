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
        """Hiển thị preview nội dung tin nhắn"""
        if len(obj.content) > 50:
            return obj.content[:50] + "..."
        return obj.content
    content_preview.short_description = "Nội dung"
    
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('message_id', 'sender', 'recipient', 'room_name')
        }),
        ('Nội dung tin nhắn', {
            'fields': ('content',)
        }),
        ('Trạng thái', {
            'fields': ('is_read', 'created_at')
        }),
    )
    
    def get_queryset(self, request):
        """Tối ưu query để tránh N+1 problem"""
        return super().get_queryset(request).select_related('sender', 'recipient')
