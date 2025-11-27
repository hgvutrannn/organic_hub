"""
Django signals for auto-indexing products in Elasticsearch
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from elasticsearch import Elasticsearch
from core.models import Product
from .documents import ProductDocument
from .config import ELASTICSEARCH_URL

logger = logging.getLogger(__name__)


def delete_product_document(product_id):
    """
    Helper function to delete a product document from Elasticsearch index
    """
    try:
        # Use Elasticsearch client directly to delete document
        es = Elasticsearch([ELASTICSEARCH_URL], timeout=5)
        index_name = ProductDocument._index._name
        
        # Delete document by ID
        es.delete(
            index=index_name,
            id=str(product_id),
            ignore=[404]  # Ignore 404 if document doesn't exist
        )
        logger.debug(f"Deleted product {product_id} from index")
    except Exception as e:
        # Log error but don't fail - document might not exist
        logger.warning(f"Error deleting product {product_id} from index: {str(e)}")


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
            delete_product_document(instance.product_id)
    except Exception as e:
        logger.error(f"Error indexing product {instance.product_id}: {str(e)}", exc_info=True)


@receiver(post_delete, sender=Product)
def delete_product_from_index(sender, instance, **kwargs):
    """
    Auto-delete product from index when deleted from database
    """
    try:
        delete_product_document(instance.product_id)
    except Exception as e:
        logger.error(f"Error deleting product {instance.product_id} from index: {str(e)}", exc_info=True)

