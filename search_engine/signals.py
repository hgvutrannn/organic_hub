"""
Django signals for auto-indexing products in Elasticsearch
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from core.models import Product
from .documents import ProductDocument

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Product)
def index_product(sender, instance, **kwargs):
    """
    Auto-index product when created or updated
    """
    try:
        # Only index active products
        if instance.is_active:
            ProductDocument().update(instance)
            logger.debug(f"Indexed product: {instance.product_id}")
        else:
            # Remove from index if product is deactivated
            ProductDocument().delete(instance)
            logger.debug(f"Removed product from index: {instance.product_id}")
    except Exception as e:
        logger.error(f"Error indexing product {instance.product_id}: {str(e)}", exc_info=True)


@receiver(post_delete, sender=Product)
def delete_product_from_index(sender, instance, **kwargs):
    """
    Auto-delete product from index when deleted from database
    """
    try:
        ProductDocument().delete(instance)
        logger.debug(f"Deleted product from index: {instance.product_id}")
    except Exception as e:
        logger.error(f"Error deleting product {instance.product_id} from index: {str(e)}", exc_info=True)

