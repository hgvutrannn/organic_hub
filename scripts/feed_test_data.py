#!/usr/bin/env python
"""
Test Data Feeder Script
Creates test data for benchmarking (products, stores, categories, certificates)
"""
import os
import sys
import django
import time
import argparse
from typing import Dict, List, Any
from decimal import Decimal

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'organic_hub.settings')
django.setup()

# Now import Django models and services
from django.db import transaction
from django.core.files.uploadedfile import SimpleUploadedFile
from core.models import (
    CustomUser, Store, Category, Product, CertificationOrganization,
    StoreVerificationRequest, StoreCertification, Address
)
from search_engine.documents import ProductDocument
from cleanup_test_data import TestDataCleanup


class TestDataFeeder:
    """Class for creating and managing test data"""
    
    def __init__(self):
        self.cleanup = TestDataCleanup()
    
    def create_test_data(
        self, 
        num_products: int, 
        num_stores: int, 
        num_categories: int, 
        num_certificates: int,
        cleanup_first: bool = True
    ) -> Dict[str, Any]:
        """Create test data for benchmarking"""
        if cleanup_first:
            self.cleanup.cleanup_existing_test_data()
        
        print(f"\n{'='*60}")
        print("Creating test data...")
        print(f"{'='*60}\n")
        
        # Sample data (all in English)
        product_names = [
            "Organic Rice", "Fresh Vegetables", "Organic Pork", "Fresh Fish",
            "Seasonal Fruits", "Fresh Milk", "Natural Honey",
            "Baked Bread", "Fruit Juice", "Organic Yogurt", "Free Range Eggs",
            "Herb-fed Beef", "Fresh Salmon", "Tiger Prawns", "Sea Crab",
            "Fresh Greens", "Cherry Tomatoes", "Bell Peppers", "Carrots", "Potatoes"
        ]
        
        product_descriptions = [
            "Certified organic product, no chemicals used",
            "Fresh and delicious vegetables, grown using natural methods",
            "Clean meat from organic farms",
            "Fresh fish caught naturally",
            "Seasonal fruits, sweet and nutritious",
            "Fresh milk from free-range cows",
            "Pure natural honey, unadulterated",
            "Delicious baked bread made from organic flour",
            "Fresh fruit juice, no artificial sweeteners",
            "Organic yogurt rich in probiotics, good for digestion"
        ]
        
        category_names = [
            "Dry Food", "Vegetables", "Meat & Fish", "Dairy Products",
            "Beverages", "Spices", "Bakery", "Frozen Food"
        ]
        
        certificate_names = [
            ("USDA Organic", "USDA"),
            ("VietGAP", "VGAP"),
            ("GlobalGAP", "GGAP"),
            ("EU Organic", "EU"),
            ("JAS Organic", "JAS")
        ]
        
        created_objects = {
            'users': [],
            'stores': [],
            'categories': [],
            'certificates': [],
            'products': [],
            'verification_requests': [],
            'store_certifications': []
        }
        
        with transaction.atomic():
            # Create test user
            test_user, created = CustomUser.objects.get_or_create(
                phone_number='+84900000000',
                defaults={
                    'email': 'benchmark@test.com',
                    'full_name': 'Benchmark Test User',
                    'is_active': True,
                    'email_verified': True
                }
            )
            created_objects['users'].append(test_user)
            
            # Create categories
            for i in range(num_categories):
                name = category_names[i % len(category_names)]
                category, _ = Category.objects.get_or_create(
                    name=f"{name} {i+1}",
                    defaults={'slug': f"{name.lower().replace(' ', '-')}-{i+1}"}
                )
                created_objects['categories'].append(category)
            
            # Create certification organizations
            for i in range(num_certificates):
                name, abbrev = certificate_names[i % len(certificate_names)]
                cert, _ = CertificationOrganization.objects.get_or_create(
                    name=f"{name} {i+1}",
                    defaults={
                        'abbreviation': f"{abbrev}{i+1}",
                        'is_active': True
                    }
                )
                created_objects['certificates'].append(cert)
            
            # Create stores with addresses
            for i in range(num_stores):
                # Create address
                address = Address.objects.create(
                    user=test_user,
                    street=f"Test Street {i+1}",
                    ward=f"Ward {i+1}",
                    province="Hanoi",
                    country="Vietnam",
                    contact_phone=f"+849{i:08d}",
                    contact_person=f"Contact Person {i+1}"
                )
                
                store = Store.objects.create(
                    user=test_user,
                    store_name=f"Test Store {i+1}",
                    store_description=f"Test store description {i+1}",
                    store_address=address,
                    is_verified_status='verified'
                )
                created_objects['stores'].append(store)
                
                # Create verification request and certifications for store
                if i < num_certificates:
                    verification_request = StoreVerificationRequest.objects.create(
                        store=store,
                        status='approved'
                    )
                    created_objects['verification_requests'].append(verification_request)
                    
                    # Link certificate to store
                    cert = created_objects['certificates'][i % len(created_objects['certificates'])]
                    # Create a dummy document file for benchmark
                    dummy_file = SimpleUploadedFile(
                        f"cert_{i+1}.pdf",
                        b"dummy certificate content for benchmark",
                        content_type="application/pdf"
                    )
                    store_cert = StoreCertification.objects.create(
                        verification_request=verification_request,
                        certification_organization=cert,
                        certification_type='organic',
                        certification_name=f"Certification {cert.name}",
                        certificate_number=f"CERT-{i+1:04d}",
                        document=dummy_file
                    )
                    created_objects['store_certifications'].append(store_cert)
            
            # Create products using bulk_create for better performance
            products_per_store = num_products // num_stores
            remaining_products = num_products % num_stores
            batch_size = 1000  # Process in batches of 1000
            total_created = 0
            
            print(f"  Creating {num_products} products in batches of {batch_size}...")
            
            for store_idx, store in enumerate(created_objects['stores']):
                products_to_create = products_per_store + (1 if store_idx < remaining_products else 0)
                
                # Create products in batches
                for batch_start in range(0, products_to_create, batch_size):
                    batch_end = min(batch_start + batch_size, products_to_create)
                    batch_products = []
                    
                    for i in range(batch_start, batch_end):
                        product_idx = store_idx * products_per_store + i
                        name = product_names[product_idx % len(product_names)]
                        description = product_descriptions[product_idx % len(product_descriptions)]
                        category = created_objects['categories'][product_idx % len(created_objects['categories'])]
                        
                        # Vary prices
                        base_price = Decimal('50000') + Decimal(str((product_idx % 20) * 10000))
                        
                        batch_products.append(Product(
                            store=store,
                            category=category,
                            name=f"{name} #{product_idx+1}",
                            description=f"{description}. Product #{product_idx+1}.",
                            price=base_price,
                            base_unit="kg" if product_idx % 2 == 0 else "pack",
                            stock=100 + (product_idx % 50),
                            SKU=f"SKU-{product_idx+1:06d}",
                            is_active=True,
                            view_count=product_idx % 1000
                        ))
                    
                    # Bulk create batch
                    created_batch = Product.objects.bulk_create(batch_products, batch_size=batch_size)
                    created_objects['products'].extend(created_batch)
                    total_created += len(created_batch)
                    
                    if total_created % 10000 == 0:
                        print(f"    Created {total_created}/{num_products} products...")
        
        print(f"✓ Created {len(created_objects['users'])} users")
        print(f"✓ Created {len(created_objects['stores'])} stores")
        print(f"✓ Created {len(created_objects['categories'])} categories")
        print(f"✓ Created {len(created_objects['certificates'])} certificates")
        print(f"✓ Created {len(created_objects['products'])} products")
        print(f"✓ Created {len(created_objects['verification_requests'])} verification requests")
        print(f"✓ Created {len(created_objects['store_certifications'])} store certifications")
        
        return created_objects
    
    def index_to_elasticsearch(self, test_data: Dict[str, Any], skip_indexing: bool = False):
        """Index products into Elasticsearch"""
        if skip_indexing:
            print(f"\n{'='*60}")
            print("Skipping Elasticsearch indexing")
            print(f"{'='*60}\n")
            return
        
        print(f"\n{'='*60}")
        print("Indexing products into Elasticsearch...")
        print(f"{'='*60}\n")
        
        try:
            ProductDocument.init()
            indexed = 0
            batch_size = 500  # Index in batches for better performance
            
            total_products = len(test_data['products'])
            print(f"  Indexing {total_products:,} products in batches of {batch_size}...")
            
            start_time = time.time()
            
            # Index products in batches
            for i in range(0, total_products, batch_size):
                batch = test_data['products'][i:i + batch_size]
                
                # Index each product in batch (django-elasticsearch-dsl doesn't have true bulk)
                for product in batch:
                    try:
                        ProductDocument().update(product)
                        indexed += 1
                    except Exception as e:
                        # Skip individual product errors
                        pass
                
                # Progress reporting with ETA
                if indexed % 5000 == 0 or indexed == total_products:
                    elapsed = time.time() - start_time
                    rate = indexed / elapsed if elapsed > 0 else 0
                    remaining = total_products - indexed
                    eta = remaining / rate if rate > 0 else 0
                    print(f"    Indexed {indexed:,}/{total_products:,} products... "
                          f"({rate:.0f} products/sec, ETA: {eta/60:.1f} min)")
            
            # Refresh index to make documents searchable immediately
            try:
                from elasticsearch_dsl import Index
                index = Index(ProductDocument._index._name)
                index.refresh()
            except:
                pass  # Refresh is optional
            
            elapsed_total = time.time() - start_time
            print(f"✓ Indexed {indexed:,} products into Elasticsearch in {elapsed_total/60:.1f} minutes")
        except Exception as e:
            print(f"⚠ Warning: Could not index into Elasticsearch: {str(e)}")
            print("  Products are created but not indexed")
            import traceback
            traceback.print_exc()
    
    def cleanup_test_data(self, test_data: Dict[str, Any], keep_data: bool = False):
        """Clean up test data"""
        self.cleanup.cleanup_test_data(test_data, keep_data=keep_data)


def main():
    """Main function for standalone data feeding"""
    parser = argparse.ArgumentParser(description='Create test data for benchmarking')
    parser.add_argument('--num-products', type=int, default=1000, help='Number of products to create (default: 1000)')
    parser.add_argument('--num-stores', type=int, default=10, help='Number of stores to create (default: 10)')
    parser.add_argument('--num-categories', type=int, default=5, help='Number of categories to create (default: 5)')
    parser.add_argument('--num-certificates', type=int, default=3, help='Number of certificates to create (default: 3)')
    parser.add_argument('--skip-indexing', action='store_true', help='Skip Elasticsearch indexing')
    parser.add_argument('--no-cleanup', action='store_true', help='Do not cleanup existing test data before creating')
    parser.add_argument('--keep-data', action='store_true', help='Keep test data (no cleanup after)')
    
    args = parser.parse_args()
    
    # Warn user about large datasets
    if args.num_products >= 50000:
        print(f"\n{'='*60}")
        print("⚠ WARNING: Large dataset detected!")
        print(f"{'='*60}")
        print(f"Creating {args.num_products:,} products may take significant time and memory.")
        print("Estimated time: 10-30 minutes depending on your system.")
        print(f"{'='*60}\n")
        
        response = input("Continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Aborted.")
            sys.exit(0)
    
    feeder = TestDataFeeder()
    
    try:
        # Create test data
        test_data = feeder.create_test_data(
            args.num_products,
            args.num_stores,
            args.num_categories,
            args.num_certificates,
            cleanup_first=not args.no_cleanup
        )
        
        # Index to Elasticsearch
        feeder.index_to_elasticsearch(test_data, skip_indexing=args.skip_indexing)
        
        print(f"\n{'='*60}")
        print("Test data creation completed successfully!")
        print(f"{'='*60}\n")
        
        if args.keep_data:
            print("Test data kept in database (use --no-keep-data to cleanup)")
        else:
            # Cleanup
            feeder.cleanup_test_data(test_data, keep_data=False)
        
    except KeyboardInterrupt:
        print("\n\nData creation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError during data creation: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

