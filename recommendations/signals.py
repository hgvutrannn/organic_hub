from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from core.models import Product
from .models import UserProductView


@receiver(post_save, sender=Product)
def track_product_view_signal(sender, instance, created, **kwargs):
    """
    This signal is triggered when a product is saved.
    Note: We'll track views manually in views.py when product_detail is accessed.
    """
    pass


def track_product_view(product, user=None, session_key=None):
    """
    Track a product view for recommendation system.
    Only tracks for authenticated users now.
    Called from product_detail view.
    """
    try:
        if user and user.is_authenticated:
            view, created = UserProductView.objects.get_or_create(
                user=user,
                product=product,
                defaults={'view_count': 1}
            )
            if not created:
                view.view_count += 1
                view.viewed_at = timezone.now()  # Update to current time
                view.save(update_fields=['view_count', 'viewed_at'])
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error tracking product view: {e}", exc_info=True)

