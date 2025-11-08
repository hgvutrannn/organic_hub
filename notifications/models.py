from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    """Represents a user facing notification persisted for history."""

    CATEGORY_ORDER_STATUS = 'order_status'

    CATEGORY_CHOICES = (
        (CATEGORY_ORDER_STATUS, 'Order status'),
    )

    SEVERITY_INFO = 'info'
    SEVERITY_SUCCESS = 'success'
    SEVERITY_WARNING = 'warning'
    SEVERITY_ERROR = 'error'

    SEVERITY_CHOICES = (
        (SEVERITY_INFO, 'Info'),
        (SEVERITY_SUCCESS, 'Success'),
        (SEVERITY_WARNING, 'Warning'),
        (SEVERITY_ERROR, 'Error'),
    )

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='Người nhận',
    )
    order = models.ForeignKey(
        'core.Order',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        verbose_name='Đơn hàng liên quan',
    )
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_ORDER_STATUS,
    )
    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        default=SEVERITY_INFO,
    )
    message = models.TextField(verbose_name='Nội dung thông báo')
    metadata = models.JSONField(blank=True, null=True, verbose_name='Metadata bổ sung')
    is_read = models.BooleanField(default=False, verbose_name='Đã đọc')
    read_at = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian đọc')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Thời gian tạo')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Thời gian cập nhật')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Thông báo'
        verbose_name_plural = 'Thông báo'

    def __str__(self):
        return f"Notification to {self.recipient_id} ({self.category})"

    def mark_as_read(self):
        """Mark the notification as read."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
