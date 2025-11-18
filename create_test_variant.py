#!/usr/bin/env python
"""
Script để tạo variant test cho sản phẩm
Usage: python create_test_variant.py <product_id>
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'organic_hub.settings')
django.setup()

from core.models import Product, ProductVariant
from decimal import Decimal

def create_test_variants(product_id):
    """Tạo variants test cho sản phẩm"""
    try:
        product = Product.objects.get(pk=product_id)
        print(f"Tìm thấy sản phẩm: {product.name}")
        print(f"has_variants hiện tại: {product.has_variants}")
        print(f"Số variants hiện có: {product.variants.count()}")
        
        # Tạo 3 variants mẫu
        variants_data = [
            {
                'variant_name': '500g',
                'price': Decimal(str(float(product.price) * 0.5)),
                'stock': 100,
                'sort_order': 1,
            },
            {
                'variant_name': '1kg',
                'price': product.price,
                'stock': 50,
                'sort_order': 2,
            },
            {
                'variant_name': '2kg',
                'price': Decimal(str(float(product.price) * 2)),
                'stock': 30,
                'sort_order': 3,
            },
        ]
        
        created_variants = []
        for data in variants_data:
            variant, created = ProductVariant.objects.get_or_create(
                product=product,
                variant_name=data['variant_name'],
                defaults={
                    'price': data['price'],
                    'stock': data['stock'],
                    'sort_order': data['sort_order'],
                    'is_active': True,
                }
            )
            if created:
                created_variants.append(variant)
                print(f"✓ Đã tạo variant: {variant.variant_name} - {variant.price} VNĐ")
            else:
                print(f"- Variant đã tồn tại: {variant.variant_name}")
        
        # Refresh product để lấy has_variants mới nhất
        product.refresh_from_db()
        print(f"\n✓ Hoàn thành!")
        print(f"has_variants sau khi tạo: {product.has_variants}")
        print(f"Tổng số variants: {product.variants.count()}")
        print(f"Số variants active: {product.variants.filter(is_active=True).count()}")
        
        return created_variants
        
    except Product.DoesNotExist:
        print(f"❌ Không tìm thấy sản phẩm với ID={product_id}")
        return []
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return []

if __name__ == '__main__':
    if len(sys.argv) > 1:
        product_id = int(sys.argv[1])
    else:
        product_id = 1  # Default
    
    create_test_variants(product_id)

