"""
Management command to update Elasticsearch index
Usage: 
  python manage.py update_search_index --product-id <id>  # Update single product
  python manage.py update_search_index --all              # Update all products
"""
from django.core.management.base import BaseCommand
from elasticsearch import Elasticsearch
from core.models import Product
from search_engine.documents import ProductDocument
from search_engine.config import ELASTICSEARCH_URL


class Command(BaseCommand):
    help = 'Update Elasticsearch index for products'

    def add_arguments(self, parser):
        parser.add_argument(
            '--product-id',
            type=int,
            help='Update specific product by ID',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Update all products',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of products to index per batch (only for --all)',
        )

    def handle(self, *args, **options):
        product_id = options.get('product_id')
        update_all = options.get('all', False)
        batch_size = options['batch_size']
        
        if product_id:
            # Update single product
            try:
                product = Product.objects.get(product_id=product_id)
                if product.is_active:
                    ProductDocument().update(product)
                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully updated product {product_id} in index.')
                    )
                else:
                    # Delete product from index using Elasticsearch client
                    try:
                        es = Elasticsearch([ELASTICSEARCH_URL], timeout=5)
                        index_name = ProductDocument._index._name
                        es.delete(
                            index=index_name,
                            id=str(product_id),
                            ignore=[404]
                        )
                        self.stdout.write(
                            self.style.SUCCESS(f'Successfully removed product {product_id} from index.')
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'Error removing product {product_id} from index: {str(e)}')
                        )
            except Product.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Product {product_id} not found.')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error updating product {product_id}: {str(e)}')
                )
        
        elif update_all:
            # Update all products
            self.stdout.write('Updating all products in index...')
            
            products = Product.objects.filter(is_active=True).select_related('category', 'store')
            total = products.count()
            
            if total == 0:
                self.stdout.write(self.style.WARNING('No products found to update.'))
                return
            
            updated = 0
            for i in range(0, total, batch_size):
                batch = list(products[i:i + batch_size])
                # Use Document's update method for each product
                for product in batch:
                    ProductDocument().update(product)
                updated += len(batch)
                self.stdout.write(f'Updated {updated}/{total} products...')
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully updated {updated} products in index.')
            )
        
        else:
            self.stdout.write(
                self.style.ERROR('Please specify --product-id <id> or --all')
            )

