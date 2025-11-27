#!/usr/bin/env python
"""
Test Data Cleanup Script
Cleans up test data created for benchmarking
"""
import os
import sys
import django
import argparse
from typing import Dict, Any, Optional

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'organic_hub.settings')
django.setup()

# Now import Django models
from django.db import transaction
from django.db.models import Q
from core.models import (
    CustomUser, Store, Category, Product, CertificationOrganization,
    StoreVerificationRequest, StoreCertification, Address
)


class TestDataCleanup:
    """Class for cleaning up test data"""
    
    def cleanup_existing_test_data(self):
        """Clean up existing test data before creating new ones"""
        print(f"\n{'='*60}")
        print("Cleaning up existing test data...")
        print(f"{'='*60}\n")
        
        try:
            # Find test user
            test_user = CustomUser.objects.filter(phone_number='+84900000000').first()
            if not test_user:
                print("  No existing test data found")
                return
            
            # Delete products with test SKU pattern
            test_products = Product.objects.filter(SKU__startswith='SKU-').filter(store__user=test_user)
            product_count = test_products.count()
            if product_count > 0:
                print(f"  Deleting {product_count} existing test products...")
                # Delete in batches
                batch_size = 1000
                product_ids = list(test_products.values_list('product_id', flat=True))
                for i in range(0, len(product_ids), batch_size):
                    batch_ids = product_ids[i:i + batch_size]
                    Product.objects.filter(product_id__in=batch_ids).delete()
                print(f"  ✓ Deleted {product_count} products")
            
            # Delete test stores
            test_stores = Store.objects.filter(user=test_user, store_name__startswith='Test Store')
            store_count = test_stores.count()
            if store_count > 0:
                print(f"  Deleting {store_count} existing test stores...")
                store_ids = list(test_stores.values_list('store_id', flat=True))
                stores = Store.objects.filter(store_id__in=store_ids).select_related('store_address')
                addresses_to_delete = [s.store_address for s in stores if s.store_address]
                if addresses_to_delete:
                    Address.objects.filter(
                        address_id__in=[a.address_id for a in addresses_to_delete]
                    ).delete()
                Store.objects.filter(store_id__in=store_ids).delete()
                print(f"  ✓ Deleted {store_count} stores")
            
            # Delete test categories (using contains for SQLite compatibility)
            category_names = ["Dry Food", "Vegetables", "Meat & Fish", "Dairy Products", 
                            "Beverages", "Spices", "Bakery", "Frozen Food"]
            category_filter = Q()
            for name in category_names:
                category_filter |= Q(name__startswith=name + " ")
            test_categories = Category.objects.filter(category_filter)
            category_count = test_categories.count()
            if category_count > 0:
                print(f"  Deleting {category_count} existing test categories...")
                Category.objects.filter(
                    category_id__in=[c.category_id for c in test_categories]
                ).delete()
                print(f"  ✓ Deleted {category_count} categories")
            
            # Delete test certificates (using contains for SQLite compatibility)
            cert_names = ["USDA Organic", "VietGAP", "GlobalGAP", "EU Organic", "JAS Organic"]
            cert_filter = Q()
            for name in cert_names:
                cert_filter |= Q(name__startswith=name + " ")
            test_certs = CertificationOrganization.objects.filter(cert_filter)
            cert_count = test_certs.count()
            if cert_count > 0:
                print(f"  Deleting {cert_count} existing test certificates...")
                # Delete related store certifications first
                StoreCertification.objects.filter(
                    certification_organization_id__in=[c.organization_id for c in test_certs]
                ).delete()
                # Delete verification requests
                StoreVerificationRequest.objects.filter(
                    store__user=test_user
                ).delete()
                # Delete certificates
                CertificationOrganization.objects.filter(
                    organization_id__in=[c.organization_id for c in test_certs]
                ).delete()
                print(f"  ✓ Deleted {cert_count} certificates")
            
            print("✓ Existing test data cleaned up")
        except Exception as e:
            print(f"  ⚠ Warning: Error cleaning up existing test data: {str(e)}")
            print("  Continuing...")
            import traceback
            traceback.print_exc()
    
    def cleanup_test_data(self, test_data: Optional[Dict[str, Any]] = None, keep_data: bool = False):
        """
        Clean up test data
        
        Args:
            test_data: Optional dict with created objects. If None, will cleanup all test data.
            keep_data: If True, skip cleanup
        """
        if keep_data:
            print("\nKeeping test data (--keep-data flag set)")
            return
        
        print(f"\n{'='*60}")
        print("Cleaning up test data...")
        print(f"{'='*60}\n")
        
        try:
            with transaction.atomic():
                if test_data:
                    # Delete specific test data objects
                    # Delete certifications
                    if test_data.get('store_certifications'):
                        StoreCertification.objects.filter(
                            certification_id__in=[c.certification_id for c in test_data['store_certifications']]
                        ).delete()
                    
                    # Delete verification requests
                    if test_data.get('verification_requests'):
                        StoreVerificationRequest.objects.filter(
                            request_id__in=[r.request_id for r in test_data['verification_requests']]
                        ).delete()
                    
                    # Delete products in batches
                    if test_data.get('products'):
                        product_ids = [p.product_id for p in test_data['products']]
                        batch_size = 1000
                        for i in range(0, len(product_ids), batch_size):
                            batch_ids = product_ids[i:i + batch_size]
                            Product.objects.filter(product_id__in=batch_ids).delete()
                            if (i + batch_size) % 10000 == 0:
                                print(f"  Deleted {min(i + batch_size, len(product_ids))}/{len(product_ids)} products...")
                    
                    # Delete stores
                    if test_data.get('stores'):
                        store_ids = [s.store_id for s in test_data['stores']]
                        stores = Store.objects.filter(store_id__in=store_ids).select_related('store_address')
                        addresses_to_delete = [s.store_address for s in stores if s.store_address]
                        if addresses_to_delete:
                            Address.objects.filter(
                                address_id__in=[a.address_id for a in addresses_to_delete]
                            ).delete()
                        Store.objects.filter(store_id__in=store_ids).delete()
                    
                    # Delete certificates
                    if test_data.get('certificates'):
                        CertificationOrganization.objects.filter(
                            organization_id__in=[c.organization_id for c in test_data['certificates']]
                        ).delete()
                    
                    # Delete categories
                    if test_data.get('categories'):
                        Category.objects.filter(
                            category_id__in=[c.category_id for c in test_data['categories']]
                        ).delete()
                else:
                    # Cleanup all test data (same as cleanup_existing_test_data)
                    self.cleanup_existing_test_data()
                    return
                
                # Keep test user for potential reuse
                print("✓ Test data cleaned up (test user kept)")
        except Exception as e:
            print(f"  ⚠ Error cleaning up test data: {str(e)}")
            import traceback
            traceback.print_exc()


def main():
    """Main function for standalone cleanup"""
    parser = argparse.ArgumentParser(description='Clean up test data for benchmarking')
    parser.add_argument('--all', action='store_true', help='Clean up all test data (default behavior)')
    parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')
    
    args = parser.parse_args()
    
    cleanup = TestDataCleanup()
    
    # Count test data before cleanup
    test_user = CustomUser.objects.filter(phone_number='+84900000000').first()
    if test_user:
        product_count = Product.objects.filter(SKU__startswith='SKU-').filter(store__user=test_user).count()
        store_count = Store.objects.filter(user=test_user, store_name__startswith='Test Store').count()
        
        if product_count == 0 and store_count == 0:
            print("No test data found to clean up.")
            return
        
        print(f"\n{'='*60}")
        print("Test Data Cleanup")
        print(f"{'='*60}")
        print(f"Found:")
        print(f"  - {product_count} test products")
        print(f"  - {store_count} test stores")
        print(f"{'='*60}\n")
        
        if not args.confirm:
            response = input("Are you sure you want to delete all test data? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("Aborted.")
                return
    
    try:
        cleanup.cleanup_existing_test_data()
        print(f"\n{'='*60}")
        print("Cleanup completed successfully!")
        print(f"{'='*60}\n")
    except Exception as e:
        print(f"\n\nError during cleanup: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

