from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class Notification(TimeStampedModel):
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
        verbose_name='Recipient',
    )
    order = models.ForeignKey(
        'core.Order',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        verbose_name='Related Order',
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
    message = models.TextField(verbose_name='Message')
    is_read = models.BooleanField(default=False, verbose_name='Is Read')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f"Notification to {self.recipient_id} ({self.category})"

    def mark_as_read(self):
        """Mark the notification as read."""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])
