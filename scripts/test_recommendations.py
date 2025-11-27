# scripts/test_recommendations.py
#!/usr/bin/env python
"""
Script để test chức năng Personalised Recommendation
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'organic_hub.settings')
django.setup()

from django.utils import timezone
from django.utils.text import slugify
from decimal import Decimal
from core.models import (
    CustomUser, Store, Category, Product, ProductImage,
    Order, OrderItem, Review, Address
)
from recommendations.models import UserProductView
from recommendations.services import RecommendationService

def setup_test_data():
    """Tạo dữ liệu test cho recommendation system"""
    
    print("="*60)
    print("Setting up test data for recommendations...")
    print("="*60)
    
    # 1. Tạo users
    user1, _ = CustomUser.objects.get_or_create(
        phone_number='0987654321',
        defaults={
            'full_name': 'Test User 1',
            'email': 'user1@test.com'
        }
    )
    
    user2, _ = CustomUser.objects.get_or_create(
        phone_number='0987654322',
        defaults={
            'full_name': 'Test User 2',
            'email': 'user2@test.com'
        }
    )
    
    print(f"✓ Created users: {user1.phone_number}, {user2.phone_number}")
    
    # 2. Tạo categories
    from django.utils.text import slugify
    
    cat1, _ = Category.objects.get_or_create(
        name='Organic Vegetables',
        defaults={'slug': slugify('Organic Vegetables')}
    )
    cat2, _ = Category.objects.get_or_create(
        name='Organic Fruits',
        defaults={'slug': slugify('Organic Fruits')}
    )
    cat3, _ = Category.objects.get_or_create(
        name='Dairy Products',
        defaults={'slug': slugify('Dairy Products')}
    )
    
    print(f"✓ Created categories: {cat1.name}, {cat2.name}, {cat3.name}")
    
    # 3. Tạo stores
    store1, _ = Store.objects.get_or_create(
        user=user1,
        defaults={
            'store_name': 'Organic Farm Store',
            'is_verified_status': 'verified'
        }
    )
    
    store2, _ = Store.objects.get_or_create(
        user=user2,
        defaults={
            'store_name': 'Fresh Market',
            'is_verified_status': 'verified'
        }
    )
    
    print(f"✓ Created stores: {store1.store_name}, {store2.store_name}")
    
    # 4. Tạo products với các categories khác nhau
    products = []
    categories = [cat1, cat1, cat2, cat2, cat3, cat3]
    prices = [50000, 75000, 100000, 120000, 80000, 90000]
    
    for i, (cat, price) in enumerate(zip(categories, prices)):
        product, _ = Product.objects.get_or_create(
            name=f'Test Product {i+1} - {cat.name}',
            store=store1 if i % 2 == 0 else store2,
            defaults={
                'category': cat,
                'description': f'Test product in {cat.name} category',
                'price': Decimal(str(price)),
                'base_unit': 'kg',
                'stock': 100,
                'is_active': True,
                'has_variants': False
            }
        )
        products.append(product)
    
    print(f"✓ Created {len(products)} products")
    
    # 5. Tạo UserProductView để track viewing history
    # User1 xem products từ cat1 và cat2
    for product in products[:4]:  # First 4 products
        UserProductView.objects.get_or_create(
            user=user1,
            product=product,
            defaults={'view_count': 3, 'viewed_at': timezone.now()}
        )
    
    # User2 xem products từ cat2 và cat3
    for product in products[2:6]:  # Products 3-6
        UserProductView.objects.get_or_create(
            user=user2,
            product=product,
            defaults={'view_count': 2, 'viewed_at': timezone.now()}
        )
    
    print(f"✓ Created product views for users")
    
    # 6. Tạo addresses và orders để simulate purchase history
    # Tạo addresses cho users
    address1, _ = Address.objects.get_or_create(
        user=user1,
        defaults={
            'street': '123 Test Street',
            'ward': 'Test Ward',
            'province': 'Ho Chi Minh City',
            'contact_phone': user1.phone_number,
            'contact_person': user1.full_name,
            'is_default': True
        }
    )
    
    address2, _ = Address.objects.get_or_create(
        user=user2,
        defaults={
            'street': '456 Test Street',
            'ward': 'Test Ward',
            'province': 'Ho Chi Minh City',
            'contact_phone': user2.phone_number,
            'contact_person': user2.full_name,
            'is_default': True
        }
    )
    
    # User1 mua products từ cat1
    if not Order.objects.filter(user=user1).exists():
        subtotal = products[0].price * 2 + products[1].price
        order1 = Order.objects.create(
            user=user1,
            status='delivered',
            subtotal=subtotal,
            total_amount=subtotal,
            payment_method='cod',
            shipping_address=address1
        )
        
        # Add order items
        OrderItem.objects.create(
            order=order1,
            product=products[0],
            quantity=2,
            unit_price=products[0].price,
            total_price=products[0].price * 2
        )
        
        OrderItem.objects.create(
            order=order1,
            product=products[1],
            quantity=1,
            unit_price=products[1].price,
            total_price=products[1].price
        )
        
        print(f"✓ Created order for {user1.phone_number}")
    
    # User2 mua products từ cat2 và cat3
    if not Order.objects.filter(user=user2).exists():
        subtotal = products[2].price + products[3].price
        order2 = Order.objects.create(
            user=user2,
            status='delivered',
            subtotal=subtotal,
            total_amount=subtotal,
            payment_method='cod',
            shipping_address=address2
        )
        
        OrderItem.objects.create(
            order=order2,
            product=products[2],
            quantity=1,
            unit_price=products[2].price,
            total_price=products[2].price
        )
        
        OrderItem.objects.create(
            order=order2,
            product=products[3],
            quantity=1,
            unit_price=products[3].price,
            total_price=products[3].price
        )
        
        print(f"✓ Created order for {user2.phone_number}")
    
    # 7. Tạo reviews để test rating boost
    for i, product in enumerate(products[:3]):
        # Get order_item for this product if exists
        order_item = None
        if i < 2:
            # User1's order
            order = Order.objects.filter(user=user1).first()
            if order:
                order_item = OrderItem.objects.filter(order=order, product=product).first()
        else:
            # User2's order
            order = Order.objects.filter(user=user2).first()
            if order:
                order_item = OrderItem.objects.filter(order=order, product=product).first()
        
        Review.objects.get_or_create(
            user=user1 if i % 2 == 0 else user2,
            product=product,
            order_item=order_item,
            defaults={
                'rating': 5 if i == 0 else 4,
                'content': f'Great product!',
                'is_approved': True
            }
        )
    
    print(f"✓ Created reviews")
    
    print("\n" + "="*60)
    print("Test data setup complete!")
    print("="*60 + "\n")
    
    return user1, user2, products

def test_recommendations():
    """Test các chức năng recommendation"""
    
    user1, user2, products = setup_test_data()
    
    print("="*60)
    print("Testing Recommendation System")
    print("="*60 + "\n")
    
    # Test 1: Personalized recommendations for User1
    print("1. Testing get_personalized_recommendations for User1:")
    print(f"   User: {user1.phone_number}")
    recs = RecommendationService.get_personalized_recommendations(user1, limit=6)
    print(f"   Found {len(recs)} recommendations:")
    for i, product in enumerate(recs, 1):
        print(f"   {i}. {product.name} (Category: {product.category.name if product.category else 'None'}, Price: {product.price})")
    print()
    
    # Test 2: Personalized recommendations for User2
    print("2. Testing get_personalized_recommendations for User2:")
    print(f"   User: {user2.phone_number}")
    recs = RecommendationService.get_personalized_recommendations(user2, limit=6)
    print(f"   Found {len(recs)} recommendations:")
    for i, product in enumerate(recs, 1):
        print(f"   {i}. {product.name} (Category: {product.category.name if product.category else 'None'}, Price: {product.price})")
    print()
    
    # Test 3: Similar products
    print("3. Testing get_similar_products:")
    test_product = products[0]
    print(f"   Product: {test_product.name}")
    similar = RecommendationService.get_similar_products(test_product, limit=4)
    print(f"   Found {len(similar)} similar products:")
    for i, product in enumerate(similar, 1):
        print(f"   {i}. {product.name} (Category: {product.category.name if product.category else 'None'})")
    print()
    
    # Test 4: Frequently bought together
    print("4. Testing get_frequently_bought_together:")
    test_product = products[0]
    print(f"   Product: {test_product.name}")
    together = RecommendationService.get_frequently_bought_together(test_product, limit=4)
    print(f"   Found {len(together)} frequently bought together products:")
    for i, product in enumerate(together, 1):
        print(f"   {i}. {product.name}")
    print()
    
    # Test 5: Best selling products
    print("5. Testing get_best_selling_products:")
    best_selling = RecommendationService.get_best_selling_products(limit=6)
    print(f"   Found {len(best_selling)} best selling products:")
    for i, product in enumerate(best_selling, 1):
        print(f"   {i}. {product.name}")
    print()
    
    # Test 6: Session recommendations (anonymous user)
    print("6. Testing get_session_recommendations:")
    session_key = "test_session_123"
    
    # Create some views for this session
    for product in products[:3]:
        UserProductView.objects.get_or_create(
            session_key=session_key,
            product=product,
            defaults={'view_count': 1, 'viewed_at': timezone.now()}
        )
    
    session_recs = RecommendationService.get_session_recommendations(session_key, limit=6)
    print(f"   Session: {session_key}")
    print(f"   Found {len(session_recs)} recommendations:")
    for i, product in enumerate(session_recs, 1):
        print(f"   {i}. {product.name} (Category: {product.category.name if product.category else 'None'})")
    print()
    
    print("="*60)
    print("All tests completed!")
    print("="*60)

if __name__ == '__main__':
    test_recommendations()