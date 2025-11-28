from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.conf import settings


class UserProductView(models.Model):
    """Track product views per user/session for recommendation system"""
    view_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='product_views',
        verbose_name='User'
    )
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Session key'
    )
    product = models.ForeignKey(
        'core.Product',
        on_delete=models.CASCADE,
        related_name='views',
        verbose_name='Product'
    )
    viewed_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name='Viewed At')
    view_count = models.PositiveIntegerField(default=1, verbose_name='View Count')

    class Meta:
        verbose_name = 'Product View'
        verbose_name_plural = 'Product Views'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'product'],
                condition=Q(user__isnull=False),
                name='unique_user_product_view'
            ),
            models.UniqueConstraint(
                fields=['session_key', 'product'],
                condition=Q(session_key__isnull=False),
                name='unique_session_product_view'
            ),
        ]
        indexes = [
            models.Index(fields=['user', 'product'], condition=Q(user__isnull=False), name='user_product_view_idx'),
            models.Index(fields=['session_key', 'product'], condition=Q(session_key__isnull=False), name='session_product_view_idx'),
            models.Index(fields=['-viewed_at'], name='viewed_at_idx'),
        ]
        ordering = ['-viewed_at']

    def __str__(self):
        if self.user:
            return f"{self.user.email} viewed {self.product.name}"
        return f"Session {self.session_key} viewed {self.product.name}"
