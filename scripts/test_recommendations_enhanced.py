#!/usr/bin/env python
"""
Enhanced Test Script for Personalised Recommendation
Tạo nhiều data hơn để test đầy đủ các scenarios
"""
import os
import sys
import django
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'organic_hub.settings')
django.setup()

from django.utils import timezone
from django.utils.text import slugify
from django.core.cache import cache
from django.db.models import Sum
from decimal import Decimal
from core.models import (
    CustomUser, Store, Category, Product, ProductImage,
    Order, OrderItem, Review, Address
)
from recommendations.models import UserProductView
from recommendations.services import RecommendationService


def setup_enhanced_test_data():
    """Tạo dữ liệu test phong phú hơn cho recommendation system"""
    
    print("="*60)
    print("Setting up ENHANCED test data for recommendations...")
    print("="*60)
    
    # Clear cache
    cache.clear()
    
    # 1. Tạo 5 users với behaviors khác nhau
    users = []
    for i in range(1, 6):
        phone = f'09876543{i:02d}'
        email = f'enhanced_user{i}@test.com'
        
        # Check if user exists
        user = CustomUser.objects.filter(phone_number=phone).first()
        if not user:
            # Check if email exists
            if CustomUser.objects.filter(email=email).exists():
                email = f'enhanced_user{i}_{phone}@test.com'
            user = CustomUser.objects.create(
                phone_number=phone,
                full_name=f'Enhanced Test User {i}',
                email=email
            )
        users.append(user)
    
    print(f"✓ Created {len(users)} users")
    
    # 2. Tạo 8 categories đa dạng
    categories_data = [
        'Organic Vegetables', 'Organic Fruits', 'Dairy Products',
        'Organic Grains', 'Organic Beverages', 'Organic Snacks',
        'Organic Meat', 'Organic Herbs'
    ]
    categories = []
    for cat_name in categories_data:
        cat, _ = Category.objects.get_or_create(
            name=cat_name,
            defaults={'slug': slugify(cat_name)}
        )
        categories.append(cat)
    
    print(f"✓ Created {len(categories)} categories")
    
    # 3. Tạo 3 stores
    stores = []
    for i, user in enumerate(users[:3]):
        store, _ = Store.objects.get_or_create(
            user=user,
            defaults={
                'store_name': f'Organic Store {i+1}',
                'is_verified_status': 'verified'
            }
        )
        stores.append(store)
    
    print(f"✓ Created {len(stores)} stores")
    
    # 4. Tạo 30 products với phân bố đều across categories và stores
    products = []
    price_ranges = [
        (30000, 50000), (50000, 80000), (80000, 120000),
        (120000, 150000), (150000, 200000)
    ]
    
    product_counter = 1
    for cat_idx, category in enumerate(categories):
        # 3-4 products per category
        num_products = 4 if cat_idx < 2 else 3
        
        for i in range(num_products):
            if product_counter > 30:
                break
                
            store = stores[product_counter % len(stores)]
            price_range = random.choice(price_ranges)
            price = Decimal(str(random.randint(price_range[0], price_range[1])))
            
            product, _ = Product.objects.get_or_create(
                name=f'Enhanced Test Product {product_counter} - {category.name}',
                store=store,
                defaults={
                    'category': category,
                    'description': f'High quality {category.name.lower()} product for testing',
                    'price': price,
                    'base_unit': 'kg' if 'Vegetables' in category.name or 'Fruits' in category.name else 'piece',
                    'stock': random.randint(50, 200),
                    'is_active': True,
                    'has_variants': False,
                    'view_count': random.randint(0, 100)
                }
            )
            products.append(product)
            product_counter += 1
    
    print(f"✓ Created {len(products)} products across {len(categories)} categories")
    
    # 5. Tạo viewing history đa dạng cho users
    # User1: xem nhiều products từ categories 0, 1, 2 (Vegetables, Fruits, Dairy)
    # User2: xem products từ categories 2, 3, 4 (Dairy, Grains, Beverages)
    # User3: xem rải rác nhiều categories
    # User4, 5: ít views hơn
    
    viewing_patterns = [
        (users[0], products[:15], 5),  # User1: xem 15 products đầu, mỗi product 5 lần
        (users[1], products[10:25], 3),  # User2: xem products 10-25, mỗi product 3 lần
        (users[2], products[5:20] + products[25:], 2),  # User3: xem rải rác
        (users[3], products[:5], 1),  # User4: ít views
        (users[4], products[20:25], 1),  # User5: ít views
    ]
    
    for user, product_list, view_count in viewing_patterns:
        for product in product_list:
            UserProductView.objects.get_or_create(
                user=user,
                product=product,
                defaults={
                    'view_count': view_count,
                    'viewed_at': timezone.now()
                }
            )
    
    print(f"✓ Created product views for {len(viewing_patterns)} users")
    
    # 6. Tạo addresses cho users
    addresses = []
    for i, user in enumerate(users):
        address, _ = Address.objects.get_or_create(
            user=user,
            defaults={
                'street': f'{100+i} Test Street',
                'ward': 'Test Ward',
                'province': 'Ho Chi Minh City',
                'contact_phone': user.phone_number,
                'contact_person': user.full_name,
                'is_default': True
            }
        )
        addresses.append(address)
    
    # 7. Tạo orders với purchase patterns đa dạng
    # User1: mua nhiều từ categories 0, 1 (Vegetables, Fruits) - price range 30k-80k
    # User2: mua từ categories 2, 3 (Dairy, Grains) - price range 50k-120k
    # User3: mua rải rác nhiều categories
    # User4, 5: ít purchases
    
    order_counter = 1
    purchase_patterns = [
        # (user, category_indices, num_orders, products_per_order)
        (users[0], [0, 1], 3, 2),  # User1: 3 orders, mỗi order 2 products từ cat 0,1
        (users[1], [2, 3], 2, 3),  # User2: 2 orders, mỗi order 3 products từ cat 2,3
        (users[2], [0, 1, 2, 3, 4], 2, 2),  # User3: 2 orders, rải rác
        (users[3], [0], 1, 1),  # User4: 1 order
        (users[4], [2], 1, 1),  # User5: 1 order
    ]
    
    for user, cat_indices, num_orders, products_per_order in purchase_patterns:
        user_products = [p for p in products if p.category and p.category.category_id in [categories[i].category_id for i in cat_indices]]
        
        for order_num in range(num_orders):
            if not user_products:
                break
                
            # Select random products for this order
            order_products = random.sample(user_products, min(products_per_order, len(user_products)))
            
            # Calculate totals
            subtotal = sum(p.price * random.randint(1, 3) for p in order_products)
            
            order = Order.objects.create(
                user=user,
                status='delivered',
                subtotal=subtotal,
                total_amount=subtotal,
                payment_method='cod',
                shipping_address=addresses[users.index(user)]
            )
            
            # Create order items
            for product in order_products:
                quantity = random.randint(1, 3)
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    unit_price=product.price,
                    total_price=product.price * quantity
                )
            
            order_counter += 1
    
    print(f"✓ Created {order_counter - 1} orders with diverse purchase patterns")
    
    # 8. Tạo reviews để test rating boost
    review_count = 0
    for user in users[:3]:  # Users 1-3 leave reviews
        user_orders = Order.objects.filter(user=user, status='delivered')
        for order in user_orders[:2]:  # Review 2 orders per user
            order_items = OrderItem.objects.filter(order=order)
            for item in order_items[:2]:  # Review 2 items per order
                Review.objects.get_or_create(
                    user=user,
                    product=item.product,
                    order_item=item,
                    defaults={
                        'order': order,
                        'rating': random.randint(4, 5),
                        'content': f'Great {item.product.name}! Highly recommended.',
                        'is_approved': True,
                        'is_verified_purchase': True
                    }
                )
                review_count += 1
    
    print(f"✓ Created {review_count} reviews")
    
    print("\n" + "="*60)
    print("Enhanced test data setup complete!")
    print("="*60 + "\n")
    
    return users, products, categories


def test_enhanced_recommendations():
    """Test các chức năng recommendation với data phong phú hơn"""
    
    users, products, categories = setup_enhanced_test_data()
    
    # Clear all caches
    cache.clear()
    
    print("="*60)
    print("Testing Recommendation System with Enhanced Data")
    print("="*60 + "\n")
    
    # Test 1: Personalized recommendations for multiple users
    print("1. TESTING PERSONALIZED RECOMMENDATIONS FOR MULTIPLE USERS:")
    print("-" * 60)
    
    for i, user in enumerate(users[:3], 1):
        # Clear user cache
        for limit in [6, 8, 12]:
            cache.delete(f'rec:user:{user.user_id}:{limit}')
        
        recs = RecommendationService.get_personalized_recommendations(user, limit=8)
        
        # Check purchased products
        purchased = set(OrderItem.objects.filter(
            order__user=user,
            order__status='delivered'
        ).values_list('product', flat=True))
        
        purchased_in_recs = [p for p in recs if p.product_id in purchased]
        
        print(f"\nUser{i} ({user.phone_number}):")
        print(f"  - Purchased: {len(purchased)} products")
        print(f"  - Recommendations: {len(recs)} products")
        print(f"  - Purchased in recs: {len(purchased_in_recs)} ❌" if purchased_in_recs else f"  - Purchased in recs: 0 ✅")
        
        if recs:
            print(f"  - Top 3 recommendations:")
            for j, p in enumerate(recs[:3], 1):
                print(f"    {j}. {p.name} (Category: {p.category.name if p.category else 'None'}, Price: {p.price})")
    
    # Test 2: Similar products với nhiều products khác nhau
    print("\n\n2. TESTING SIMILAR PRODUCTS:")
    print("-" * 60)
    
    test_products = random.sample(products, min(5, len(products)))
    for product in test_products:
        cache.delete(f'rec:product:{product.product_id}:similar:6')
        similar = RecommendationService.get_similar_products(product, limit=6)
        
        # Check if product itself is in list
        self_in_list = any(p.product_id == product.product_id for p in similar)
        duplicates = len(similar) - len(set(p.product_id for p in similar))
        
        print(f"\nProduct: {product.name}")
        print(f"  - Similar products: {len(similar)}")
        print(f"  - Product itself in list: {'❌ YES' if self_in_list else '✅ NO'}")
        print(f"  - Duplicates: {duplicates} {'❌' if duplicates > 0 else '✅'}")
        
        if similar:
            print(f"  - Top 3 similar:")
            for j, p in enumerate(similar[:3], 1):
                print(f"    {j}. {p.name} (Category: {p.category.name if p.category else 'None'})")
        break  # Just test one for brevity
    
    # Test 3: Frequently bought together
    print("\n\n3. TESTING FREQUENTLY BOUGHT TOGETHER:")
    print("-" * 60)
    
    # Test with products that have orders
    products_with_orders = Product.objects.filter(
        order_items__isnull=False
    ).distinct()[:3]
    
    for product in products_with_orders:
        cache.delete(f'rec:product:{product.product_id}:together:6')
        together = RecommendationService.get_frequently_bought_together(product, limit=6)
        
        self_in_list = any(p.product_id == product.product_id for p in together)
        duplicates = len(together) - len(set(p.product_id for p in together))
        
        print(f"\nProduct: {product.name}")
        print(f"  - Frequently bought together: {len(together)}")
        print(f"  - Product itself in list: {'❌ YES' if self_in_list else '✅ NO'}")
        print(f"  - Duplicates: {duplicates} {'❌' if duplicates > 0 else '✅'}")
        
        if together:
            print(f"  - Top 3 together:")
            for j, p in enumerate(together[:3], 1):
                print(f"    {j}. {p.name}")
        break  # Just test one
    
    # Test 4: Session recommendations với nhiều sessions
    print("\n\n4. TESTING SESSION RECOMMENDATIONS:")
    print("-" * 60)
    
    session_keys = ['session_alpha', 'session_beta', 'session_gamma']
    for session_key in session_keys:
        # Create views for this session
        viewed_products = random.sample(list(products), min(5, len(products)))
        for product in viewed_products:
            UserProductView.objects.get_or_create(
                session_key=session_key,
                product=product,
                defaults={'view_count': 1, 'viewed_at': timezone.now()}
            )
        
        cache.delete(f'rec:session:{session_key}:6')
        recs = RecommendationService.get_session_recommendations(session_key, limit=6)
        
        viewed_ids = {v.product.product_id for v in UserProductView.objects.filter(session_key=session_key)}
        viewed_in_recs = [p for p in recs if p.product_id in viewed_ids]
        duplicates = len(recs) - len(set(p.product_id for p in recs))
        
        print(f"\nSession: {session_key}")
        print(f"  - Viewed products: {len(viewed_ids)}")
        print(f"  - Recommendations: {len(recs)}")
        print(f"  - Viewed in recs: {len(viewed_in_recs)} {'❌' if viewed_in_recs else '✅'}")
        print(f"  - Duplicates: {duplicates} {'❌' if duplicates > 0 else '✅'}")
        break  # Just test one
    
    # Test 5: Best selling
    print("\n\n5. TESTING BEST SELLING PRODUCTS:")
    print("-" * 60)
    best_selling = RecommendationService.get_best_selling_products(limit=10)
    print(f"Found {len(best_selling)} best selling products")
    print("Top 5:")
    for i, p in enumerate(best_selling[:5], 1):
        total_sold = OrderItem.objects.filter(product=p).aggregate(
            total=Sum('quantity')
        )['total'] or 0
        print(f"  {i}. {p.name} (Sold: {total_sold})")
    
    # Summary
    print("\n" + "="*60)
    print("ENHANCED TEST SUMMARY")
    print("="*60)
    print(f"✓ Tested with {len(users)} users")
    print(f"✓ Tested with {len(products)} products")
    print(f"✓ Tested with {len(categories)} categories")
    print(f"✓ Tested personalized, similar, frequently bought, session, and best selling")
    print("="*60)


if __name__ == '__main__':
    test_enhanced_recommendations()

