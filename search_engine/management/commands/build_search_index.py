"""
Management command to build Elasticsearch index for all products
Usage: python manage.py build_search_index
"""
from django.core.management.base import BaseCommand
from core.models import Product
from search_engine.documents import ProductDocument


class Command(BaseCommand):
    help = 'Build Elasticsearch index for all products'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of products to index per batch',
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        
        self.stdout.write('Creating Elasticsearch index...')
        
        # Create index
        ProductDocument.init()
        
        self.stdout.write('Indexing products...')
        
        # Get all active products
        products = Product.objects.filter(is_active=True).select_related('category', 'store')
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
            self.style.SUCCESS(f'Successfully indexed {indexed} products.')
        )

