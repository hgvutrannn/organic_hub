from django.db import models
from django.utils import timezone
from core.models import CustomUser

class Message(models.Model):
    message_id = models.AutoField(primary_key=True)
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_messages', verbose_name='Người gửi')
    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='received_messages', verbose_name='Người nhận')
    content = models.TextField(verbose_name='Nội dung tin nhắn')
    room_name = models.CharField(max_length=255, verbose_name='Tên phòng chat')
    is_read = models.BooleanField(default=False, verbose_name='Đã đọc')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Thời gian gửi')
    
    class Meta:
        verbose_name = 'Tin nhắn'
        verbose_name_plural = 'Tin nhắn'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Tin nhắn từ {self.sender.full_name} đến {self.recipient.full_name}"
