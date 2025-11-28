from django.db import models
from django.utils import timezone
from core.models import CustomUser

class Message(models.Model):
    message_id = models.AutoField(primary_key=True)
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_messages', verbose_name='Sender')
    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='received_messages', verbose_name='Recipient')
    content = models.TextField(verbose_name='Message Content')
    room_name = models.CharField(max_length=255, verbose_name='Room Name')
    is_read = models.BooleanField(default=False, verbose_name='Is Read')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Sent At')
    
    class Meta:
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Message from {self.sender.full_name} to {self.recipient.full_name}"
