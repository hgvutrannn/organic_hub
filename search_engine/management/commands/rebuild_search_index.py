"""
Management command to rebuild Elasticsearch index (delete and recreate)
Usage: python manage.py rebuild_search_index
"""
from django.core.management.base import BaseCommand
from search_engine.documents import ProductDocument
from core.models import Product


class Command(BaseCommand):
    help = 'Rebuild Elasticsearch index (delete and recreate)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of products to index per batch',
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        
        self.stdout.write('Deleting existing Elasticsearch index...')
        
        # Delete index if exists
        try:
            ProductDocument._index.delete(ignore=[404])
            self.stdout.write(self.style.SUCCESS('Index deleted.'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Error deleting index: {str(e)}'))
        
        self.stdout.write('Creating new Elasticsearch index...')
        
        # Create new index
        ProductDocument.init()
        
        self.stdout.write('Indexing products...')
        
        # Get all products
        products = Product.objects.all().select_related('category', 'store')
        total = products.count()
        
        if total == 0:
            self.stdout.write(self.style.WARNING('No products found to index.'))
            return
        
        # Index products in batches
        indexed = 0
        for i in range(0, total, batch_size):
            batch = list(products[i:i + batch_size])
            # Use Document's update method for each product
            for product in batch:
                ProductDocument().update(product)
            indexed += len(batch)
            self.stdout.write(f'Indexed {indexed}/{total} products...')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully rebuilt index with {indexed} products.')
        )

