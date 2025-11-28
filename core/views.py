import re
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Max, F
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from .models import (
    CustomUser, Product, 
    Category, CartItem, Order, OrderItem, Review, Address, Store, 
    ProductImage, StoreCertification, StoreVerificationRequest,
    ReviewMedia, StoreReviewStats, ProductVariant,
    FlashSale, FlashSaleProduct, DiscountCode, DiscountCodeProduct,
    CertificationOrganization
)
from .marketing_views import (
    store_flash_sale_list, store_flash_sale_create, store_flash_sale_edit, store_flash_sale_delete,
    store_discount_code_list, store_discount_code_create, store_discount_code_edit, store_discount_code_delete,
    get_store_products_ajax
)
from .forms import (
    CustomUserRegistrationForm, LoginForm, ProductForm, AddressForm, ReviewForm, SearchForm, ProfileUpdateForm,
    StoreCertificationForm, AdminStoreReviewForm, PasswordChangeForm, ForgotPasswordForm, 
    PasswordResetConfirmForm, OTPVerificationForm,
    ReviewReplyForm, StoreReviewFilterForm,
    CategoryForm, CertificationOrganizationForm
)
from chat.models import Message
from notifications.tasks import create_order_status_notifications
from datetime import timedelta
from django.db.models import Avg, Count, Q


# Helper Functions for Permissions and Business Logic
def has_user_purchased_product(user, product):
    """Check if user has purchased a specific product"""
    return OrderItem.objects.filter(
        order__user=user,
        product=product,
        order__status='delivered'
    ).exists()


def get_user_purchased_products(user):
    """Get list of products user has purchased"""
    return Product.objects.filter(
        order_items__order__user=user,
        order_items__order__status='delivered'
    ).distinct()


def can_create_review(user, order_item):
    """Check if user can create review for an order item"""
    if not user.is_authenticated:
        return False
    if order_item.order.user != user:
        return False
    if order_item.order.status != 'delivered':
        return False
    # Check if review already exists
    return not Review.objects.filter(user=user, order_item=order_item).exists()


def can_reply_review(user, review):
    """Check if user can reply to a review (must be shop owner and not already replied)"""
    if not user.is_authenticated:
        return False
    if review.product.store.user != user:
        return False
    return not review.has_seller_reply


def update_store_review_stats(store):
    """Update store review statistics"""
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    # Get reviews in last 30 days
    reviews_30d = Review.objects.filter(
        product__store=store,
        created_at__gte=thirty_days_ago,
        is_approved=True
    )
    
    total_reviews_30d = reviews_30d.count()
    avg_rating_30d = reviews_30d.aggregate(Avg('rating'))['rating__avg'] or 0.00
    good_reviews_count = reviews_30d.filter(rating__gte=4).count()
    negative_reviews_count = reviews_30d.filter(rating__lte=2).count()
    
    # Get or create stats
    stats, created = StoreReviewStats.objects.get_or_create(store=store)
    stats.total_reviews_30d = total_reviews_30d
    stats.avg_rating_30d = round(avg_rating_30d, 2)
    stats.good_reviews_count = good_reviews_count
    stats.negative_reviews_count = negative_reviews_count
    stats.save()
    
    return stats


def get_recent_reviews_since_last_access(store):
    """Get reviews created since last access"""
    stats, created = StoreReviewStats.objects.get_or_create(store=store)
    
    if stats.last_accessed_at:
        return Review.objects.filter(
            product__store=store,
            created_at__gt=stats.last_accessed_at,
            is_approved=True
        ).order_by('-created_at')
    else:
        # If never accessed, return empty queryset
        return Review.objects.none()


def get_negative_reviews_needing_reply(store):
    """Get negative reviews (1-2 stars) that need reply"""
    return Review.objects.filter(
        product__store=store,
        rating__lte=2,
        seller_reply__isnull=True,
        is_approved=True
    ).order_by('-created_at')


# Home Page
def home(request):
    """Home page - display categories and recommended products"""
    from recommendations.services import RecommendationService
    
    categories = Category.objects.all()[:12]  # Display maximum 12 categories
    
    # Get all products in ongoing flash sales, sorted by flash sale end_date (ending soonest first)
    now = timezone.now()
    flash_sale_products_queryset = FlashSaleProduct.objects.filter(
        flash_sale__is_active=True,
        flash_sale__start_date__lte=now,
        flash_sale__end_date__gte=now
    ).select_related(
        'product', 
        'product__store', 
        'product__category',
        'flash_sale',
        'flash_sale__store'
    ).order_by('flash_sale__end_date', 'created_at')[:20]  # Limit to 20 products
    
    # Calculate discount percentage and time remaining for each product
    flash_sale_products = []
    for flash_product in flash_sale_products_queryset:
        discount_percent = 0
        if flash_product.product.price > flash_product.flash_price:
            discount_percent = round(
                ((float(flash_product.product.price) - float(flash_product.flash_price)) / float(flash_product.product.price)) * 100,
                0
            )
        
        # Calculate time remaining
        time_remaining = flash_product.flash_sale.end_date - now
        total_seconds = int(time_remaining.total_seconds())
        
        if total_seconds > 0:
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            minutes = (total_seconds % 3600) // 60
            
            # Format time remaining
            if days > 0:
                time_remaining_display = f"{days} days {hours} hours"
            elif hours > 0:
                time_remaining_display = f"{hours} hours {minutes} minutes"
            else:
                time_remaining_display = f"{minutes} minutes"
        else:
            time_remaining_display = "Ended"
        
        flash_sale_products.append({
            'flash_product': flash_product,
            'discount_percent': int(discount_percent),
            'time_remaining_display': time_remaining_display
        })
    
    # Get personalized recommendations
    try:
        if request.user.is_authenticated:
            suggested_products = RecommendationService.get_personalized_recommendations(
                request.user, limit=12
            )
        else:
            # Get session key for anonymous users
            session_key = request.session.session_key
            if not session_key:
                request.session.create()
                session_key = request.session.session_key
            suggested_products = RecommendationService.get_session_recommendations(
                session_key, limit=12
            )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting recommendations in home view: {e}", exc_info=True)
        # Fallback to best selling
        suggested_products = RecommendationService.get_best_selling_products(limit=12)
    
    context = {
        'categories': categories,
        'suggested_products': suggested_products,
        'flash_sale_products': flash_sale_products,
    }
    return render(request, 'core/home.html', context)


# Authentication Views
def register(request):
    """User registration"""
    if request.method == 'POST':
        form = CustomUserRegistrationForm(request.POST)
        if form.is_valid():
            # Create user with email_verified=False
            user = form.save(commit=False)
            user.email_verified = False
            user.save()
            
            # Generate and send OTP via OTP Service
            from otp_service.service import OTPService
            result = OTPService.generate_and_send_otp(user, purpose='registration')
            
            if result['success']:
                messages.success(request, 'Registration successful! Please check your email to verify your account.')
                return redirect('otp_service:verify', user_id=user.user_id)
            else:
                messages.error(request, 'Error sending OTP. Please try again.')
    else:
        form = CustomUserRegistrationForm()
    
    return render(request, 'core/register.html', {'form': form})


def user_login(request):
    """User login"""
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, username=email, password=password)
            
            if user is not None:
                # Check if email is verified
                if not user.email_verified:
                    messages.warning(request, 'Please verify your email before logging in.')
                    return redirect('otp_service:verify', user_id=user.user_id)
                
                # Email verified, allow login
                login(request, user)
                user.save()
                messages.success(request, f'Welcome {user.full_name}!')
                return redirect('home')
            else:
                messages.error(request, 'Email or password is incorrect.')
    else:
        form = LoginForm()
    
    return render(request, 'core/login.html', {'form': form})


def user_logout(request):
    """User logout"""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('home')


# Product Views
def product_list(request):
    """Product list"""
    from django.conf import settings
    from search_engine.services import ProductSearchService
    import logging
    
    logger = logging.getLogger(__name__)
    categories = Category.objects.all()
    certificates = CertificationOrganization.objects.all()
    
    # Search and filter
    search_form = SearchForm(request.GET)
    query = None
    category = None
    certificate = None  
    min_price = None
    max_price = None
    
    if search_form.is_valid():
        query = search_form.cleaned_data.get('query')
        category = search_form.cleaned_data.get('category')
        certificate = search_form.cleaned_data.get('certificate')  
        min_price = search_form.cleaned_data.get('min_price')
        max_price = search_form.cleaned_data.get('max_price')
    
    # Try Elasticsearch search first if enabled
    use_elasticsearch = getattr(settings, 'USE_ELASTICSEARCH', True)
    products_queryset = None
    search_method_used = None
    
    # Debug: Print search parameters
    print(f"\n{'='*60}")
    print(f"🔍 SEARCH DEBUG - Query: '{query}'")
    print(f"   Category: {category}")
    print(f"   Certificate: {certificate}")  # THÊM DÒNG NÀY
    print(f"   USE_ELASTICSEARCH setting: {use_elasticsearch}")
    print(f"{'='*60}\n")
    
    if use_elasticsearch and query:
        try:
            # Build filters dict
            filters = {}
            if category:
                filters['category_id'] = category.category_id
            if certificate:  # THÊM ĐIỀU KIỆN NÀY
                filters['certificate_id'] = certificate.organization_id
            if min_price:
                filters['min_price'] = min_price
            if max_price:
                filters['max_price'] = max_price
            
            print(f"🚀 Attempting Elasticsearch search with filters: {filters}")
            
            # Use Elasticsearch search with fallback
            products_list = ProductSearchService.search_with_fallback(
                query=query,
                filters=filters,
                size=1000,
                use_elasticsearch=True
            )
            
            products_queryset = products_list
            search_method_used = 'Elasticsearch'
            print(f"✅ SUCCESS: Using Elasticsearch - Found {len(products_list)} products")
            logger.info(f"Using Elasticsearch for query: '{query}' - Found {len(products_list)} products")
            
        except Exception as e:
            print(f"❌ ERROR: Elasticsearch search failed: {str(e)}")
            import traceback
            traceback.print_exc()
            logger.warning(f"Elasticsearch search failed, using Django ORM fallback: {str(e)}")
            logger.exception(e)
            use_elasticsearch = False
    
    # Fallback to Django ORM search (original method)
    if not use_elasticsearch or products_queryset is None:
        print(f"🔄 Falling back to Django ORM search")
        products = Product.objects.all()
        
        if query:
            products = products.filter(
                Q(name__icontains=query) | Q(description__icontains=query)
            )
        if category:
            products = products.filter(category=category)


        # FIX THIS LINE - Filter correctly through relationship
        if certificate:
            # Iterate through each product
            products_to_exclude = []
        
            for product in products:
                # Which store does this product belong to?
                store_id = product.store_id
                
                flag = 0
                
                # Does that store have a cert matching the certificate?
                # Get approved requests for the store
                verification_requests = StoreVerificationRequest.objects.filter(
                    store_id=store_id,
                    status='approved'  # status is CharField, use 'approved' not True
                )
                
                for verification_request in verification_requests:
                    # Get certifications in the approved request
                    certs = StoreCertification.objects.filter(
                        verification_request=verification_request,
                        certification_organization=certificate  # Compare with CertificationOrganization object
                    )
                    
                    # Check if any certification is still valid (not expired)
                    for cert in certs:
                        # Check if certification is still valid
                        if cert.expiry_date is None or cert.expiry_date >= timezone.now().date():
                            flag = 1
                            break
                    
                    if flag == 1:
                        break
                
                # If no matching certification found, mark for removal
                if flag == 0:
                    products_to_exclude.append(product.product_id)
        
            # Remove products without certification
            products = products.exclude(product_id__in=products_to_exclude)

        if min_price:
            products = products.filter(price__gte=min_price)
        if max_price:
            products = products.filter(price__lte=max_price)
        
        products_queryset = products
        if query:
            search_method_used = 'Django ORM'
            count = products.count()
            print(f"✅ Using Django ORM - Found {count} products")
            logger.info(f"Using Django ORM for query: '{query}' - Found {count} products")
    
    print(f"📊 Final search method: {search_method_used}")
    print(f"{'='*60}\n")
    
    # Pagination
    # Handle both QuerySet and list
    if isinstance(products_queryset, list):
        # For list, use manual pagination
        paginator = Paginator(products_queryset, 12)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
    else:
        # For QuerySet, use standard pagination
        paginator = Paginator(products_queryset, 12)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'search_form': search_form,
        'search_method': search_method_used,  # For debugging
        'certificates': certificates,
    }
    return render(request, 'core/product_list.html', context)


def product_detail(request, product_id):
    """Product detail"""
    from recommendations.services import RecommendationService
    from recommendations.signals import track_product_view
    
    product = get_object_or_404(Product, pk=product_id)
    
    # Increment view count
    product.view_count += 1
    product.save()
    
    # Track product view for recommendations
    try:
        if request.user.is_authenticated:
            track_product_view(product, user=request.user)
        else:
            session_key = request.session.session_key
            if not session_key:
                request.session.create()
                session_key = request.session.session_key
            track_product_view(product, session_key=session_key)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error tracking product view: {e}", exc_info=True)
    
    # Get variants if available
    variants = []
    default_variant = None
    
    if product.has_variants:
        variants_queryset = ProductVariant.objects.filter(product=product, is_active=True).order_by('created_at')
        if variants_queryset.exists():
            variants = list(variants_queryset)
            default_variant = variants[0]  # Get first variant as default
    
    # Create image list including variant images
    gallery_images = []
    image_index = 1
    
    # Add product gallery images (order=0 is primary image)
    for img in product.get_images(primary_only=False):
        gallery_images.append({
            'type': 'product',
            'url': img.image.url,
            'alt': img.alt_text or product.name,
            'index': image_index,
        })
        image_index += 1
    
    # Add variant images (only variants with their own images)
    variant_images_map = {}  # Map to find variant from image index
    for variant in variants:
        if variant.image:
            gallery_images.append({
                'type': 'variant',
                'url': variant.image.url,
                'alt': f"{product.name} - {variant.variant_name}",
                'index': image_index,
                'variant_id': variant.variant_id,
                'variant_name': variant.variant_name,
            })
            variant_images_map[image_index] = variant.variant_id
            image_index += 1
    
    # Get reviews
    reviews = Review.objects.filter(product=product, is_approved=True).select_related('user').prefetch_related('media_files').order_by('-created_at')
    
    # Get recommendations
    try:
        similar_products = RecommendationService.get_similar_products(product, limit=8)
        frequently_bought_together = RecommendationService.get_frequently_bought_together(product, limit=4)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting recommendations in product_detail: {e}", exc_info=True)
        # Fallback to best selling
        similar_products = RecommendationService.get_best_selling_products(limit=8)
        frequently_bought_together = RecommendationService.get_best_selling_products(limit=4)
    
    context = {
        'product': product,
        'variants': variants,
        'default_variant': default_variant,
        'gallery_images': gallery_images,
        'variant_images_map': variant_images_map,
        'reviews': reviews,
        'similar_products': similar_products,
        'frequently_bought_together': frequently_bought_together,
    }
    return render(request, 'core/product_detail.html', context)


# Cart Views
@login_required
def get_store_discount_codes(request, store_id):
    """API endpoint to get available discount codes for a store (active)"""
    try:
        store = Store.objects.get(store_id=store_id)
        now = timezone.now()
        
        # Get active discount codes
        discount_codes = DiscountCode.objects.filter(
            store=store,
            status='active',
            is_active=True,
            start_date__lte=now,
            end_date__gte=now
        ).filter(
            Q(max_usage=0) | Q(used_count__lt=F('max_usage'))
        ).order_by('-created_at')
        
        codes_data = []
        for code in discount_codes:
            codes_data.append({
                'code': code.code,
                'name': code.name,
                'description': code.description or '',
                'discount_type': code.discount_type,
                'discount_value': float(code.discount_value),
                'max_discount': float(code.max_discount_amount) if code.max_discount_amount else None,
            })
        
        return JsonResponse({
            'success': True,
            'discount_codes': codes_data
        })
    except Store.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Store not found'
        }, status=404)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting discount codes: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def cart(request):
    """Shopping Cart - Grouped by Store"""
    from recommendations.services import RecommendationService
    
    cart_items = CartItem.objects.filter(user=request.user).select_related('product', 'product__store', 'variant')
    
    # Group cart items by store
    stores_dict = {}
    for item in cart_items:
        store = item.product.store
        if store.store_id not in stores_dict:
            stores_dict[store.store_id] = {
                'store': store,
                'items': []
            }
        stores_dict[store.store_id]['items'].append(item)
    
    # Calculate totals
    total = sum(item.total_price for item in cart_items)
    
    # Get recommendations based on cart items
    try:
        # Get products from cart
        cart_product_ids = [item.product.product_id for item in cart_items]
        
        # Get recommendations based on cart products
        if cart_product_ids:
            # Get frequently bought together products
            recommended_products = []
            for item in cart_items[:3]:  # Check first 3 products
                together = RecommendationService.get_frequently_bought_together(
                    item.product, limit=4
                )
                recommended_products.extend(together)
            
            # Remove duplicates and products already in cart
            seen = set(cart_product_ids)
            unique_recommended = []
            for p in recommended_products:
                if p.product_id not in seen:
                    seen.add(p.product_id)
                    unique_recommended.append(p)
                if len(unique_recommended) >= 8:
                    break
            
            # If not enough, fill with personalized recommendations
            if len(unique_recommended) < 8:
                remaining = 8 - len(unique_recommended)
                personalized = RecommendationService.get_personalized_recommendations(
                    request.user, limit=remaining
                )
                for p in personalized:
                    if p.product_id not in seen:
                        unique_recommended.append(p)
                    if len(unique_recommended) >= 8:
                        break
            
            recommendations = unique_recommended[:8]
        else:
            # Empty cart, show personalized recommendations
            recommendations = RecommendationService.get_personalized_recommendations(
                request.user, limit=8
            )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting recommendations in cart view: {e}", exc_info=True)
        # Fallback to best selling
        recommendations = RecommendationService.get_best_selling_products(limit=8)
    
    context = {
        'cart_items': cart_items,
        'stores_dict': stores_dict,
        'total': total,
        'recommendations': recommendations,
    }
    return render(request, 'core/user/cart.html', context)


@login_required
@require_POST
def add_to_cart(request, product_id):
    """Add product to cart"""
    product = get_object_or_404(Product, pk=product_id)
    quantity = int(request.POST.get('quantity', 1))
    variant_id = request.POST.get('variant_id')
    
    variant = None
    if variant_id:
        variant = get_object_or_404(ProductVariant, pk=variant_id, product=product, is_active=True)
        # Check stock
        if variant.stock < quantity:
            messages.error(request, f'Only {variant.stock} items left in stock.')
            return redirect('product_detail', product_id=product_id)
    
    cart_item, created = CartItem.objects.get_or_create(
        user=request.user,
        product=product,
        variant=variant,
        defaults={'quantity': quantity}
    )
    
    if not created:
        cart_item.quantity += quantity
        cart_item.save()
    
    messages.success(request, f'Added {product.name} to cart.')
    return redirect('product_detail', product_id=product_id)


@login_required
@require_POST
def remove_from_cart(request, cart_item_id):
    """Remove product from cart"""
    cart_item = get_object_or_404(CartItem, pk=cart_item_id, user=request.user)
    cart_item.delete()
    messages.success(request, 'Product removed from cart.')
    return redirect('cart')


@login_required
@require_POST
def update_cart_quantity(request, cart_item_id):
    """Update cart quantity"""
    cart_item = get_object_or_404(CartItem, pk=cart_item_id, user=request.user)
    quantity = int(request.POST.get('quantity', 1))
    
    if quantity > 0:
        cart_item.quantity = quantity
        cart_item.save()
    else:
        cart_item.delete()
    
    return redirect('cart')




# Order Views
@login_required
def checkout(request):
    """Checkout"""
    cart_items = CartItem.objects.filter(user=request.user).select_related('product', 'product__store', 'variant')
    
    if not cart_items.exists():
        messages.warning(request, 'Cart is empty.')
        return redirect('cart')
    
    addresses = Address.objects.filter(user=request.user)
    
    # Group cart items by store
    stores_dict = {}
    for item in cart_items:
        store = item.product.store
        if store.store_id not in stores_dict:
            stores_dict[store.store_id] = {
                'store': store,
                'items': []
            }
        stores_dict[store.store_id]['items'].append(item)
    
    # Calculate totals and store subtotals
    subtotal = sum(item.total_price for item in cart_items)
    store_subtotals = {}
    for store_id, store_data in stores_dict.items():
        store_subtotals[store_id] = sum(item.total_price for item in store_data['items'])
    
    # Get applied discounts from request.GET (passed from cart via JavaScript)
    import json
    applied_discounts = {}
    if request.method == 'GET':
        discount_data = request.GET.get('discounts', '{}')
        try:
            applied_discounts = json.loads(discount_data)
        except:
            applied_discounts = {}
    
    # Calculate discount for each store
    from decimal import Decimal
    total_discount = Decimal('0')
    store_discounts = {}
    for store_id, store_data in stores_dict.items():
        store_id_str = str(store_id)
        if store_id_str in applied_discounts:
            discount = applied_discounts[store_id_str]
            store_total = store_subtotals[store_id]
            
            discount_amount = Decimal('0')
            if discount.get('discount_type') == 'percentage':
                discount_amount = Decimal(str(store_total)) * Decimal(str(discount.get('discount_value', 0))) / Decimal('100')
                if discount.get('max_discount') and discount_amount > Decimal(str(discount.get('max_discount'))):
                    discount_amount = Decimal(str(discount.get('max_discount')))
            elif discount.get('discount_type') == 'fixed':
                discount_amount = Decimal(str(discount.get('discount_value', 0)))
            
            store_discounts[store_id] = float(discount_amount)  # Store as float for template
            total_discount += discount_amount
    
    if request.method == 'POST':
        shipping_address_id = request.POST.get('shipping_address')
        payment_method = request.POST.get('payment_method', 'cod')
        
        # Get discounts from POST data
        import json
        discount_data = request.POST.get('applied_discounts', '{}')
        try:
            applied_discounts = json.loads(discount_data)
        except:
            applied_discounts = {}
        
        if not shipping_address_id:
            messages.error(request, 'Please select a shipping address.')
            # Recalculate discounts for display
            from decimal import Decimal
            total_discount = Decimal('0')
            store_discounts = {}
            for store_id, store_data in stores_dict.items():
                store_id_str = str(store_id)
                if store_id_str in applied_discounts:
                    discount = applied_discounts[store_id_str]
                    store_total = store_subtotals[store_id]
                    
                    discount_amount = Decimal('0')
                    if discount.get('discount_type') == 'percentage':
                        discount_amount = Decimal(str(store_total)) * Decimal(str(discount.get('discount_value', 0))) / Decimal('100')
                        if discount.get('max_discount') and discount_amount > Decimal(str(discount.get('max_discount'))):
                            discount_amount = Decimal(str(discount.get('max_discount')))
                    elif discount.get('discount_type') == 'fixed':
                        discount_amount = Decimal(str(discount.get('discount_value', 0)))
                    
                    store_discounts[store_id] = float(discount_amount)  # Store as float for template
                    total_discount += discount_amount
            
            # Prepare store data for template
            stores_data = []
            for store_id, store_data in stores_dict.items():
                stores_data.append({
                    'store': store_data['store'],
                    'items': store_data['items'],
                    'subtotal': store_subtotals.get(store_id, 0),
                    'discount': store_discounts.get(store_id, 0),
                })
            
            from decimal import Decimal
            # Flat shipping fee in GBP
            shipping_cost = Decimal('3.00')
            final_total = subtotal - total_discount + shipping_cost
            
            # Load last checkout info from session
            last_checkout_info = request.session.get('last_checkout_info', {})
            default_address_id = last_checkout_info.get('shipping_address_id')
            default_payment_method = last_checkout_info.get('payment_method', 'cod')
            default_notes = last_checkout_info.get('notes', '')
            
            return render(request, 'core/user/checkout.html', {
                'cart_items': cart_items,
                'stores_dict': stores_dict,
                'stores_data': stores_data,
                'addresses': addresses,
                'subtotal': subtotal,
                'total_discount': total_discount,
                'shipping_cost': shipping_cost,
                'final_total': final_total,
                'default_address_id': default_address_id,
                'default_payment_method': default_payment_method,
                'default_notes': default_notes,
            })
        
        shipping_address = get_object_or_404(Address, pk=shipping_address_id, user=request.user)
        
        # Recalculate discounts for order
        from decimal import Decimal
        total_discount = Decimal('0')
        store_discounts = {}
        for store_id, store_data in stores_dict.items():
            store_id_str = str(store_id)
            if store_id_str in applied_discounts:
                discount = applied_discounts[store_id_str]
                store_total = store_subtotals[store_id]
                
                discount_amount = Decimal('0')
                if discount.get('discount_type') == 'percentage':
                    discount_amount = Decimal(str(store_total)) * Decimal(str(discount.get('discount_value', 0))) / Decimal('100')
                    if discount.get('max_discount') and discount_amount > Decimal(str(discount.get('max_discount'))):
                        discount_amount = Decimal(str(discount.get('max_discount')))
                elif discount.get('discount_type') == 'fixed':
                    discount_amount = Decimal(str(discount.get('discount_value', 0)))
                
                store_discounts[store_id] = float(discount_amount)  # Store as float for template
                total_discount += discount_amount
        
        # Create order for each store (each store has a separate order)
        # Flat shipping fee in GBP per order
        shipping_cost = Decimal('3.00')
        notes = request.POST.get('notes', '')
        created_orders = []
        
        for store_id, store_data in stores_dict.items():
            # Calculate subtotal and discount for this store
            store_subtotal = store_subtotals[store_id]
            store_discount = Decimal(str(store_discounts.get(store_id, 0)))
            store_total = store_subtotal - store_discount + shipping_cost
            
            # Create order for this store
            order = Order.objects.create(
                user=request.user,
                shipping_address=shipping_address,
                subtotal=store_subtotal,
                discount_amount=store_discount,
                shipping_cost=shipping_cost,
                total_amount=store_total,
                payment_method=payment_method,
                notes=notes
            )
            
            # Create order items for this store
            for cart_item in store_data['items']:
                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    variant=cart_item.variant,
                    quantity=cart_item.quantity,
                    unit_price=cart_item.unit_price,
                    total_price=cart_item.total_price
                )
            
            created_orders.append(order)
        
        # Clear cart
        cart_items.delete()
        
        # Save checkout info to session for next time
        request.session['last_checkout_info'] = {
            'shipping_address_id': shipping_address_id,
            'payment_method': payment_method,
            'notes': notes,
        }
        
        # Display message with all order IDs
        order_ids = ', '.join([f'#{order.order_id}' for order in created_orders])
        if len(created_orders) == 1:
            messages.success(request, f'Order placed successfully! Order ID: {order_ids}')
            return redirect('order_detail', order_id=created_orders[0].order_id)
        else:
            messages.success(request, f'Order placed successfully! Created {len(created_orders)} orders: {order_ids}')
            # Redirect to order list
            return redirect('orders')
    
    # Get frequently bought together recommendations
    from recommendations.services import RecommendationService
    
    try:
        # Get products from cart
        cart_product_ids = [item.product.product_id for item in cart_items]
        
        # Get frequently bought together products
        recommended_products = []
        for item in cart_items[:3]:  # Check first 3 products
            together = RecommendationService.get_frequently_bought_together(
                item.product, limit=4
            )
            recommended_products.extend(together)
        
        # Remove duplicates and products already in cart
        seen = set(cart_product_ids)
        unique_recommended = []
        for p in recommended_products:
            if p.product_id not in seen:
                seen.add(p.product_id)
                unique_recommended.append(p)
            if len(unique_recommended) >= 6:
                break
        
        # If not enough, fill with best selling
        if len(unique_recommended) < 6:
            remaining = 6 - len(unique_recommended)
            best_selling = RecommendationService.get_best_selling_products(limit=remaining)
            for p in best_selling:
                if p.product_id not in seen:
                    unique_recommended.append(p)
                if len(unique_recommended) >= 6:
                    break
        
        recommendations = unique_recommended[:6]
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting recommendations in checkout view: {e}", exc_info=True)
        # Fallback to best selling
        recommendations = RecommendationService.get_best_selling_products(limit=6)
    
    # Prepare store data with subtotals and discounts for template
    stores_data = []
    for store_id, store_data in stores_dict.items():
        stores_data.append({
            'store': store_data['store'],
            'items': store_data['items'],
            'subtotal': store_subtotals.get(store_id, 0),
            'discount': store_discounts.get(store_id, 0),
        })
    
    # Calculate final total
    from decimal import Decimal
    # Flat shipping fee in GBP
    shipping_cost = Decimal('3.00')
    final_total = subtotal - total_discount + shipping_cost
    
    # Load last checkout info from session to pre-fill form
    last_checkout_info = request.session.get('last_checkout_info', {})
    default_address_id = last_checkout_info.get('shipping_address_id')
    default_payment_method = last_checkout_info.get('payment_method', 'cod')
    default_notes = last_checkout_info.get('notes', '')
    
    context = {
        'cart_items': cart_items,
        'stores_dict': stores_dict,
        'stores_data': stores_data,
        'addresses': addresses,
        'subtotal': subtotal,
        'total_discount': total_discount,
        'shipping_cost': shipping_cost,
        'final_total': final_total,
        'recommendations': recommendations,
        'default_address_id': default_address_id,
        'default_payment_method': default_payment_method,
        'default_notes': default_notes,
    }
    return render(request, 'core/user/checkout.html', context)


@login_required
def order_list(request):
    """Order list"""
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'orders': orders,
    }
    return render(request, 'core/user/orders.html', context)


@login_required
def order_detail(request, order_id):
    """Order detail"""
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    
    # Group order items by store
    stores_dict = {}
    for item in order.order_items.select_related('product', 'product__store', 'variant').all():
        store = item.product.store
        if store.store_id not in stores_dict:
            stores_dict[store.store_id] = {
                'store': store,
                'items': []
            }
        stores_dict[store.store_id]['items'].append(item)
    
    # Get reviews for order items and group by store
    stores_data = []
    for store_id, store_data in stores_dict.items():
        store_items_with_reviews = []
        store_subtotal = 0
        
        for item in store_data['items']:
            review = Review.objects.filter(user=request.user, order_item=item).first()
            can_review = can_create_review(request.user, item) if order.status == 'delivered' else False
            store_items_with_reviews.append({
                'item': item,
                'review': review,
                'can_review': can_review,
            })
            store_subtotal += item.total_price
        
        stores_data.append({
            'store': store_data['store'],
            'items_with_reviews': store_items_with_reviews,
            'subtotal': store_subtotal,
        })
    
    context = {
        'order': order,
        'stores_data': stores_data,
    }
    return render(request, 'core/user/order_detail.html', context)




# Profile Views
@login_required
def profile(request):
    """User profile"""
    user = request.user
    recent_orders = Order.objects.filter(user=user).order_by('-created_at')[:5]
    
    # Check if user has any stores
    user_stores = Store.objects.filter(user=user)
    has_store = user_stores.exists()
    
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        form = ProfileUpdateForm(instance=user)
    
    context = {
        'user': user,
        'recent_orders': recent_orders,
        'user_stores': user_stores,
        'has_store': has_store,
        'form': form,
    }
    return render(request, 'core/user/profile.html', context)


@login_required
def address_management(request):
    """Address management"""
    addresses = Address.objects.filter(user=request.user)
    
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            messages.success(request, 'Address added successfully.')
            return redirect('address_management')
    else:
        form = AddressForm()
    
    context = {
        'addresses': addresses,
        'form': form,
    }
    return render(request, 'core/user/address_management.html', context)


# Store Views
@login_required
def create_store(request):
    """Create store with certification"""
    if request.method == 'POST':
        store_name = request.POST.get('store_name')
        store_description = request.POST.get('store_description', '')
        
        if store_name:
            # Create store
            store = Store.objects.create(
                user=request.user,
                store_name=store_name,
                store_description=store_description,
                is_verified_status='pending'
            )
            
            # Handle certification uploads
            certification_files = request.FILES.getlist('certification_files')
            certificate_numbers = request.POST.getlist('certificate_numbers')
            issue_dates = request.POST.getlist('issue_dates')
            expiry_dates = request.POST.getlist('expiry_dates')
            certification_organizations = request.POST.getlist('certification_organizations')
            
            # Create verification request
            verification_request = StoreVerificationRequest.objects.create(
                store=store,
                status='pending'
            )
            
            # Create certification records - ensure we have matching data
            if certification_files:
                min_length = len(certification_files)
                for i in range(min_length):
                    file = certification_files[i]
                    cert_number = certificate_numbers[i] if i < len(certificate_numbers) and certificate_numbers[i] else ''
                    issue_date_str = issue_dates[i] if i < len(issue_dates) and issue_dates[i] else None
                    expiry_date_str = expiry_dates[i] if i < len(expiry_dates) and expiry_dates[i] else None
                    org_id = certification_organizations[i] if i < len(certification_organizations) and certification_organizations[i] else None
                    
                    if file:  # Only create if file is provided
                        try:
                            cert_data = {
                                'verification_request': verification_request,
                                'certificate_number': cert_number,
                                'document': file,
                            }
                            
                            # Parse dates
                            if issue_date_str:
                                try:
                                    from datetime import datetime
                                    cert_data['issue_date'] = datetime.strptime(issue_date_str, '%Y-%m-%d').date()
                                except ValueError:
                                    pass
                            
                            if expiry_date_str:
                                try:
                                    from datetime import datetime
                                    cert_data['expiry_date'] = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
                                except ValueError:
                                    pass
                            
                            # Add organization if provided
                            if org_id:
                                try:
                                    org = CertificationOrganization.objects.get(organization_id=org_id, is_active=True)
                                    cert_data['certification_organization'] = org
                                except CertificationOrganization.DoesNotExist:
                                    pass
                            
                            StoreCertification.objects.create(**cert_data)
                        except Exception as e:
                            print(f"Error creating certification: {e}")
            
            messages.success(request, f'Store "{store_name}" created successfully! Verification request has been sent.')
            return redirect('store_dashboard', store_id=store.store_id)
        else:
            messages.error(request, 'Please enter store name.')
    
    # Get active certification organizations for dropdown
    certification_organizations = CertificationOrganization.objects.filter(is_active=True).order_by('name')
    
    context = {
        'certification_organizations': certification_organizations,
    }
    return render(request, 'core/store/create_store.html', context)


@login_required
def store_dashboard(request, store_id):
    """Store dashboard"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    products = Product.objects.filter(store=store)
    orders = Order.objects.filter(order_items__product__store=store).distinct().order_by('-created_at')[:10]
    
    # Get verification requests
    verification_requests = store.verification_requests.all()
    latest_request = verification_requests.first()
    
    # Basic statistics
    total_products = products.count()
    total_orders = orders.count()
    total_revenue = sum(order.total_amount for order in orders if order.payment_status == 'paid')
    
    context = {
        'store': store,
        'products': products[:5],  # 5 most recent products
        'orders': orders,
        'total_products': total_products,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'verification_requests': verification_requests,
        'latest_request': latest_request,
    }
    return render(request, 'core/store/store_dashboard.html', context)


@login_required
def store_products(request, store_id):
    """Store product management"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    products = Product.objects.filter(store=store).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(products, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'store': store,
        'products': page_obj,
    }
    return render(request, 'core/store/store_products.html', context)


@login_required
def add_product(request, store_id):
    """Add new product"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    
    # Check if store is verified
    if store.is_verified_status != 'verified':
        messages.error(request, 'Store must be verified before adding products.')
        return redirect('store_dashboard', store_id=store.store_id)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.store = store
            has_variants = form.cleaned_data.get('has_variants', False)
            product.has_variants = has_variants
            
            # Handle price: if has_variants and price is 0 or empty, set to 0
            if has_variants:
                # Price can be 0 when has variants (price managed by variants)
                if not product.price or product.price == 0:
                    product.price = 0
            # If no variants, price should already be set from form
            
            # If no variants, stock is required
            if not has_variants:
                stock = request.POST.get('stock', 0)
                try:
                    product.stock = int(stock)
                except (ValueError, TypeError):
                    product.stock = 0
            else:
                # If has variants, stock should be 0 (stock managed by variants)
                product.stock = 0
            
            # Save product first to get product_id
            product.save()
            
            # Auto-generate SKU if not provided
            if not product.SKU:
                # Generate unique SKU
                max_attempts = 10
                for _ in range(max_attempts):
                    sku = f"PROD-{product.store.store_id}-{uuid.uuid4().hex[:8].upper()}"
                    if not Product.objects.filter(SKU=sku).exclude(pk=product.pk).exists():
                        product.SKU = sku
                        product.save(update_fields=['SKU'])
                        break
                # If still no SKU after attempts, use product_id
                if not product.SKU:
                    product.SKU = f"PROD-{product.store.store_id}-{product.product_id}"
                    product.save(update_fields=['SKU'])
            
            # Handle multiple gallery images
            gallery_images = request.FILES.getlist('gallery_images')
            for i, image in enumerate(gallery_images[:10]):  # Limit to 10 images
                ProductImage.objects.create(
                    product=product,
                    image=image,
                    alt_text=f"{product.name} - Image {i+1}",
                    order=i  # First image is order=0 (primary), then 1, 2, 3...
                )
            
            # Handle variants if has_variants is enabled
            if has_variants:
                # Process variants from form data
                variants_data = {}
                for key, value in request.POST.items():
                    if key.startswith('variants['):
                        # Extract variant index and field name
                        # Format: variants[index][field_name]
                        match = re.match(r'variants\[(\d+)\]\[(\w+)\]', key)
                        if match:
                            idx = match.group(1)
                            field = match.group(2)
                            if idx not in variants_data:
                                variants_data[idx] = {}
                            variants_data[idx][field] = value
                
                # Process variant images
                variant_images = {}
                for key, file in request.FILES.items():
                    if key.startswith('variants['):
                        match = re.match(r'variants\[(\d+)\]\[image\]', key)
                        if match:
                            idx = match.group(1)
                            variant_images[idx] = file
                
                # Create variants
                created_variants = 0
                for idx, variant_data in variants_data.items():
                    variant_name = variant_data.get('variant_name', '').strip()
                    if not variant_name:
                        continue
                    
                    try:
                        price = float(variant_data.get('price', 0))
                        stock = int(variant_data.get('stock', 0))
                        sku_code = variant_data.get('sku_code', '').strip()
                        variant_description = variant_data.get('variant_description', '').strip()
                        variant_image = variant_images.get(idx)
                        
                        variant = ProductVariant.objects.create(
                            product=product,
                            variant_name=variant_name,
                            variant_description=variant_description if variant_description else None,
                            price=price,
                            stock=stock,
                            sku_code=sku_code if sku_code else None,
                            image=variant_image
                        )
                        
                        # Auto-generate SKU if not provided
                        if not variant.sku_code:
                            variant.sku_code = f"{product.SKU or product.product_id}-{uuid.uuid4().hex[:8].upper()}"
                            variant.save(update_fields=['sku_code'])
                        
                        created_variants += 1
                    except (ValueError, TypeError) as e:
                        continue
                
                if created_variants > 0:
                    messages.success(request, f'Product "{product.name}" added successfully with {created_variants} variants!')
                else:
                    messages.warning(request, f'Product "{product.name}" added but no variants yet. Please edit the product to add variants.')
            else:
                messages.success(request, f'Product "{product.name}" added successfully!')
            
            return redirect('store_products', store_id=store.store_id)
        else:
            messages.error(request, 'Please check the information again.')
    else:
        form = ProductForm()
    
    categories = Category.objects.all()
    context = {
        'store': store,
        'categories': categories,
        'form': form,
        'product': None,  # For template logic
    }
    return render(request, 'core/store/product_form.html', context)


@login_required
def edit_product(request, store_id, product_id):
    """Edit product"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    product = get_object_or_404(Product, pk=product_id, store=store)
    # Check if store is verified
    if store.is_verified_status != 'verified':
        messages.error(request, 'Store must be verified before editing products.')
        return redirect('store_dashboard', store_id=store.store_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'delete':
            product.delete()
            messages.success(request, f'Product "{product.name}" deleted successfully!')
            return redirect('store_products', store_id=store.store_id)
        elif action == 'update':
            form = ProductForm(request.POST, request.FILES, instance=product)
            if form.is_valid():
                has_variants = form.cleaned_data.get('has_variants', False)
                
                # Handle stock based on has_variants
                if not has_variants:
                    stock = request.POST.get('stock', 0)
                    try:
                        product.stock = int(stock)
                    except (ValueError, TypeError):
                        product.stock = 0
                else:
                    # If has variants, stock should be 0 (stock managed by variants)
                    product.stock = 0
                
                form.save()
                
                # Auto-generate SKU if not provided (only for existing products that don't have SKU)
                if not product.SKU:
                    # Generate unique SKU
                    max_attempts = 10
                    for _ in range(max_attempts):
                        sku = f"PROD-{product.store.store_id}-{uuid.uuid4().hex[:8].upper()}"
                        if not Product.objects.filter(SKU=sku).exclude(pk=product.pk).exists():
                            product.SKU = sku
                            product.save(update_fields=['SKU'])
                            break
                    # If still no SKU after attempts, use product_id
                    if not product.SKU:
                        product.SKU = f"PROD-{product.store.store_id}-{product.product_id}"
                        product.save(update_fields=['SKU'])
                
                # Handle variants if has_variants is enabled and variants are submitted
                if has_variants:
                    # Process variants from form data
                    variants_data = {}
                    for key, value in request.POST.items():
                        if key.startswith('variants['):
                            # Extract variant index and field name
                            match = re.match(r'variants\[(\d+)\]\[(\w+)\]', key)
                            if match:
                                idx = match.group(1)
                                field = match.group(2)
                                if idx not in variants_data:
                                    variants_data[idx] = {}
                                variants_data[idx][field] = value
                
                    # Process variant images
                    variant_images = {}
                    for key, file in request.FILES.items():
                        if key.startswith('variants['):
                            match = re.match(r'variants\[(\d+)\]\[image\]', key)
                            if match:
                                idx = match.group(1)
                                variant_images[idx] = file
                    
                    # Handle delete variants
                    delete_variant_ids = request.POST.getlist('delete_variants')
                    if delete_variant_ids:
                        ProductVariant.objects.filter(
                            product=product,
                            variant_id__in=delete_variant_ids
                        ).delete()
                    
                    # Process variants: update existing or create new
                    updated_variants = 0
                    created_variants = 0
                    
                    for idx, variant_data in variants_data.items():
                        variant_name = variant_data.get('variant_name', '').strip()
                        if not variant_name:
                            continue
                        
                        variant_id = variant_data.get('variant_id', '').strip()
                        
                        try:
                            price = float(variant_data.get('price', 0))
                            stock = int(variant_data.get('stock', 0))
                            sku_code = variant_data.get('sku_code', '').strip()
                            variant_description = variant_data.get('variant_description', '').strip()
                            variant_image = variant_images.get(idx)
                            
                            if variant_id:
                                # Update existing variant
                                try:
                                    variant = ProductVariant.objects.get(
                                        variant_id=int(variant_id),
                                        product=product
                                    )
                                    variant.variant_name = variant_name
                                    variant.variant_description = variant_description if variant_description else None
                                    variant.price = price
                                    variant.stock = stock
                                    if sku_code:
                                        variant.sku_code = sku_code
                                    if variant_image:
                                        variant.image = variant_image
                                    variant.save()
                                    updated_variants += 1
                                except (ProductVariant.DoesNotExist, ValueError):
                                    continue
                            else:
                                # Create new variant
                                variant = ProductVariant.objects.create(
                                    product=product,
                                    variant_name=variant_name,
                                    variant_description=variant_description if variant_description else None,
                                    price=price,
                                    stock=stock,
                                    sku_code=sku_code if sku_code else None,
                                    image=variant_image
                                )
                                
                                # Auto-generate SKU if not provided
                                if not variant.sku_code:
                                    variant.sku_code = f"{product.SKU or product.product_id}-{uuid.uuid4().hex[:8].upper()}"
                                    variant.save(update_fields=['sku_code'])
                                
                                created_variants += 1
                        except (ValueError, TypeError) as e:
                            continue
                    
                    if created_variants > 0 or updated_variants > 0:
                        messages.success(request, f'Updated {updated_variants} variants and created {created_variants} new variants.')
            
                # Handle additional gallery images
                gallery_images = request.FILES.getlist('gallery_images')
                if gallery_images:
                    # Get current max order
                    max_order = product.images.aggregate(Max('order'))['order__max']
                    if max_order is None:
                        # No images exist, start from 0
                        start_order = 0
                    else:
                        # Continue from max_order + 1
                        start_order = max_order + 1
                    
                    for i, image in enumerate(gallery_images[:10]):  # Limit to 10 images
                        ProductImage.objects.create(
                            product=product,
                            image=image,
                            alt_text=f"{product.name} - Image {start_order + i + 1}",
                            order=start_order + i
                        )
                
                messages.success(request, f'Product "{product.name}" updated successfully!')
                return redirect('edit_product', store_id=store.store_id, product_id=product.product_id)
            else:
                messages.error(request, 'Please check the information again.')
    else:
        form = ProductForm(instance=product)
    
    categories = Category.objects.all()
    variants = ProductVariant.objects.filter(product=product).order_by('created_at')
    context = {
        'store': store,
        'product': product,
        'categories': categories,
        'form': form,
        'variants': variants,
    }
    return render(request, 'core/store/product_form.html', context)


# Variant Management Views
@login_required
def get_variant_info(request, variant_id):
    """AJAX endpoint to get variant information"""
    variant = get_object_or_404(ProductVariant, pk=variant_id, is_active=True)
    
    return JsonResponse({
        'success': True,
        'variant_id': variant.variant_id,
        'variant_name': variant.variant_name,
        'price': str(variant.price),
        'stock': variant.stock,
        'image_url': variant.display_image.url if variant.display_image else None,
        'is_in_stock': variant.is_in_stock,
    })


@login_required
def get_product_variants(request, product_id):
    """AJAX endpoint to get product variants list"""
    product = get_object_or_404(Product, pk=product_id)
    
    if not product.has_variants:
        return JsonResponse({'success': False, 'message': 'Product does not have variants'})
    
    variants = ProductVariant.objects.filter(product=product, is_active=True).order_by('created_at')
    variants_data = []
    
    for variant in variants:
        variants_data.append({
            'variant_id': variant.variant_id,
            'variant_name': variant.variant_name,
            'price': str(variant.price),
            'stock': variant.stock,
            'image_url': variant.display_image.url if variant.display_image else None,
            'is_in_stock': variant.is_in_stock,
        })
    
    return JsonResponse({
        'success': True,
        'variants': variants_data,
    })




@login_required
def store_orders(request, store_id):
    """View store orders"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    orders = Order.objects.filter(order_items__product__store=store).distinct().order_by('-created_at')
    
    # Pagination
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'store': store,
        'orders': page_obj,
    }
    return render(request, 'core/store/store_orders.html', context)


@login_required
def store_order_detail(request, store_id, order_id):
    """Store order detail"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    order = get_object_or_404(Order, pk=order_id)
    
    # Get store products in the order
    store_order_items = order.order_items.filter(product__store=store)
    
    if not store_order_items.exists():
        messages.error(request, 'This order does not contain products from your store.')
        return redirect('store_orders', store_id=store.store_id)
    
    # Calculate store total in the order
    store_subtotal = sum(item.total_price for item in store_order_items)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in ['pending', 'waiting_pickup', 'shipping', 'delivered', 'cancelled']:
            previous_status = order.status
            if previous_status != new_status:
                order.status = new_status
                order.save(update_fields=['status'])
                create_order_status_notifications.delay(
                    order_id=order.order_id,
                    new_status=new_status,
                    triggered_by_id=request.user.user_id,
                )
                messages.success(request, f'Order status updated to "{order.get_status_display()}"')
            else:
                messages.info(request, 'Order status unchanged.')
            return redirect('store_order_detail', store_id=store.store_id, order_id=order.order_id)
    
    context = {
        'store': store,
        'order': order,
        'store_order_items': store_order_items,
        'store_subtotal': store_subtotal,
    }
    return render(request, 'core/store/store_order_detail.html', context)


@login_required
def verification_status(request, store_id):
    """Store verification status page"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    verification_requests = store.verification_requests.all()
    
    context = {
        'store': store,
        'verification_requests': verification_requests,
    }
    return render(request, 'core/store/verification_status.html', context)


@login_required
def verification_management(request, store_id):
    """Store verification management page"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    verification_requests = store.verification_requests.all()
    latest_request = verification_requests.first()
    
    # Check if user can send new request
    can_send_new_request = True
    if latest_request and latest_request.status == 'pending':
        can_send_new_request = False
    
    if request.method == 'POST':
        # Handle new verification request
        if can_send_new_request:
            certification_files = request.FILES.getlist('certification_files')
            certification_organizations = request.POST.getlist('certification_organizations')
            
            if certification_files:
                # Create new verification request
                verification_request = StoreVerificationRequest.objects.create(
                    store=store,
                    status='pending'
                )
                
                # Create certification records
                for i in range(len(certification_files)):
                    file = certification_files[i]
                    org_id = certification_organizations[i] if i < len(certification_organizations) and certification_organizations[i] else None
                    
                    if file:
                        try:
                            cert_data = {
                                'verification_request': verification_request,
                                'document': file
                            }
                            # Add organization if provided
                            if org_id:
                                try:
                                    org = CertificationOrganization.objects.get(organization_id=org_id, is_active=True)
                                    cert_data['certification_organization'] = org
                                except CertificationOrganization.DoesNotExist:
                                    pass
                            
                            StoreCertification.objects.create(**cert_data)
                        except Exception as e:
                            print(f"Error creating certification: {e}")
                
                messages.success(request, f'New verification request #{verification_request.request_id} sent successfully!')
                return redirect('verification_management', store_id=store.store_id)
            else:
                messages.error(request, 'Please upload at least one certification.')
        else:
            messages.error(request, 'You cannot send a new request while there is a pending request.')
    
    # Get active certification organizations for dropdown
    certification_organizations = CertificationOrganization.objects.filter(is_active=True).order_by('name')
    
    context = {
        'store': store,
        'verification_requests': verification_requests,
        'latest_request': latest_request,
        'can_send_new_request': can_send_new_request,
        'certification_organizations': certification_organizations,
    }
    return render(request, 'core/store/verification_management.html', context)


# Admin Views
def admin_required(user):
    """Check if user is admin (staff or superuser)"""
    return user.is_authenticated and (user.is_staff or user.is_superuser)


@login_required
@user_passes_test(admin_required)
def admin_dashboard(request):
    """Admin dashboard for reviewing stores"""
    # Get verification requests with different statuses
    pending_requests = StoreVerificationRequest.objects.filter(status='pending').order_by('-submitted_at')
    all_requests = StoreVerificationRequest.objects.all().order_by('-submitted_at')
    
    # Statistics
    total_requests = StoreVerificationRequest.objects.count()
    pending_count = pending_requests.count()
    approved_count = StoreVerificationRequest.objects.filter(status='approved').count()
    rejected_count = StoreVerificationRequest.objects.filter(status='rejected').count()
    
    # Pagination for all requests
    paginator = Paginator(all_requests, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'pending_requests': pending_requests,
        'all_requests': page_obj,
        'total_requests': total_requests,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
    }
    return render(request, 'core/admin/admin_dashboard.html', context)


@login_required
@user_passes_test(admin_required)
def admin_store_detail(request, store_id):
    """Admin view for reviewing a specific store and its verification requests"""
    store = get_object_or_404(Store, store_id=store_id)
    verification_requests = store.verification_requests.all()
    
    context = {
        'store': store,
        'verification_requests': verification_requests,
    }
    return render(request, 'core/admin/admin_store_detail.html', context)


@login_required
@user_passes_test(admin_required)
def admin_request_detail(request, request_id):
    """Admin view for reviewing a specific verification request"""
    verification_request = get_object_or_404(StoreVerificationRequest, request_id=request_id)
    certifications = verification_request.certifications.all()
    
    if request.method == 'POST':
        form = AdminStoreReviewForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            admin_notes = form.cleaned_data['admin_notes']
            
            if action == 'approve':
                verification_request.status = 'approved'
                verification_request.reviewed_at = timezone.now()
                verification_request.reviewed_by = request.user
                verification_request.admin_notes = admin_notes
                verification_request.save()
                
                # Update store status
                store = verification_request.store
                store.is_verified_status = 'verified'
                store.save()
                
                messages.success(request, f'Verification request approved for store "{store.store_name}"')
            else:  # reject
                verification_request.status = 'rejected'
                verification_request.reviewed_at = timezone.now()
                verification_request.reviewed_by = request.user
                verification_request.admin_notes = admin_notes
                verification_request.save()
                
                messages.success(request, f'Verification request rejected for store "{verification_request.store.store_name}"')
            
            return redirect('admin_request_detail', request_id=verification_request.request_id)
    else:
        form = AdminStoreReviewForm()
    
    context = {
        'verification_request': verification_request,
        'certifications': certifications,
        'form': form,
    }
    return render(request, 'core/admin/admin_request_detail.html', context)


@login_required
@user_passes_test(admin_required)
@require_POST
def admin_approve_store(request, store_id):
    """Approve a store"""
    store = get_object_or_404(Store, store_id=store_id)
    store.is_verified_status = 'verified'
    store.save()
    
    # Mark all certifications as verified
    store.certifications.update(is_verified=True)
    
    messages.success(request, f'Store "{store.store_name}" approved')
    return redirect('admin_store_detail', store_id=store.store_id)


@login_required
@user_passes_test(admin_required)
@require_POST
def admin_reject_store(request, store_id):
    """Reject a store with notes"""
    store = get_object_or_404(Store, store_id=store_id)
    admin_notes = request.POST.get('admin_notes', '')
    
    if not admin_notes:
        messages.error(request, 'Please enter the reason for rejection.')
        return redirect('admin_store_detail', store_id=store.store_id)
    
    store.is_verified_status = 'rejected'
    store.save()
    
    messages.success(request, f'Store "{store.store_name}" rejected')
    return redirect('admin_store_detail', store_id=store.store_id)


# Category Management Views
@login_required
@user_passes_test(admin_required)
def admin_category_list(request):
    """List all categories"""
    categories = Category.objects.all().order_by('name')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        categories = categories.filter(
            Q(name__icontains=search_query) | Q(slug__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(categories, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'categories': page_obj,
        'search_query': search_query,
        'total_categories': Category.objects.count(),
    }
    return render(request, 'core/admin/category_list.html', context)


@login_required
@user_passes_test(admin_required)
def admin_category_create(request):
    """Create a new category"""
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Category "{category.name}" created successfully!')
            return redirect('admin_category_list')
    else:
        form = CategoryForm()
    
    context = {
        'form': form,
        'action': 'create',
    }
    return render(request, 'core/admin/category_form.html', context)


@login_required
@user_passes_test(admin_required)
def admin_category_edit(request, category_id):
    """Edit an existing category"""
    category = get_object_or_404(Category, category_id=category_id)
    
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Category "{category.name}" updated successfully!')
            return redirect('admin_category_list')
    else:
        form = CategoryForm(instance=category)
    
    context = {
        'form': form,
        'category': category,
        'action': 'edit',
    }
    return render(request, 'core/admin/category_form.html', context)


@login_required
@user_passes_test(admin_required)
@require_POST
def admin_category_delete(request, category_id):
    """Delete a category"""
    category = get_object_or_404(Category, category_id=category_id)
    category_name = category.name
    
    # Check if category has products
    product_count = category.products.count()
    if product_count > 0:
        messages.error(request, f'Cannot delete category "{category_name}" because {product_count} products are using this category.')
        return redirect('admin_category_list')
    
    category.delete()
    messages.success(request, f'Category "{category_name}" deleted successfully!')
    return redirect('admin_category_list')


# Certification Organization Management Views
@login_required
@user_passes_test(admin_required)
def admin_certification_organization_list(request):
    """List all certification organizations"""
    organizations = CertificationOrganization.objects.all().order_by('name')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        organizations = organizations.filter(
            Q(name__icontains=search_query) | Q(abbreviation__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(organizations, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'organizations': page_obj,
        'search_query': search_query,
        'total_organizations': CertificationOrganization.objects.count(),
    }
    return render(request, 'core/admin/certification_organization_list.html', context)


@login_required
@user_passes_test(admin_required)
def admin_certification_organization_create(request):
    """Create a new certification organization"""
    if request.method == 'POST':
        form = CertificationOrganizationForm(request.POST)
        if form.is_valid():
            organization = form.save()
            messages.success(request, f'Organization "{organization.name}" created successfully!')
            return redirect('admin_certification_organization_list')
    else:
        form = CertificationOrganizationForm()
    
    context = {
        'form': form,
        'action': 'create',
    }
    return render(request, 'core/admin/certification_organization_form.html', context)


@login_required
@user_passes_test(admin_required)
def admin_certification_organization_edit(request, organization_id):
    """Edit an existing certification organization"""
    organization = get_object_or_404(CertificationOrganization, organization_id=organization_id)
    
    if request.method == 'POST':
        form = CertificationOrganizationForm(request.POST, instance=organization)
        if form.is_valid():
            organization = form.save()
            messages.success(request, f'Organization "{organization.name}" updated successfully!')
            return redirect('admin_certification_organization_list')
    else:
        form = CertificationOrganizationForm(instance=organization)
    
    context = {
        'form': form,
        'organization': organization,
        'action': 'edit',
    }
    return render(request, 'core/admin/certification_organization_form.html', context)


@login_required
@user_passes_test(admin_required)
@require_POST
def admin_certification_organization_delete(request, organization_id):
    """Delete a certification organization"""
    organization = get_object_or_404(CertificationOrganization, organization_id=organization_id)
    organization_name = organization.name
    
    organization.delete()
    messages.success(request, f'Organization "{organization_name}" deleted successfully!')
    return redirect('admin_certification_organization_list')


# Product Comment Views
# Review Views
@login_required
def create_review(request, order_id, order_item_id):
    """Create a review for an order item"""
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    order_item = get_object_or_404(OrderItem, pk=order_item_id, order=order)
    
    if not can_create_review(request.user, order_item):
        messages.error(request, 'You cannot review this product.')
        return redirect('order_detail', order_id=order_id)
    
    if request.method == 'POST':
        form = ReviewForm(request.POST, request.FILES)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            review.product = order_item.product
            review.order = order
            review.order_item = order_item
            review.save()
            
            # Handle image uploads
            images = request.FILES.getlist('images')
            for idx, image in enumerate(images):
                ReviewMedia.objects.create(
                    review=review,
                    file=image,
                    media_type='image',
                    order=idx
                )
            
            # Handle video uploads
            videos = request.FILES.getlist('videos')
            for idx, video in enumerate(videos):
                ReviewMedia.objects.create(
                    review=review,
                    file=video,
                    media_type='video',
                    order=len(images) + idx
                )
            
            # Update store review stats
            update_store_review_stats(order_item.product.store)
            
            messages.success(request, 'Review created successfully!')
            return redirect('order_detail', order_id=order_id)
        else:
            messages.error(request, 'Please check the information again.')
    else:
        form = ReviewForm()
    
    context = {
        'order': order,
        'order_item': order_item,
        'form': form,
    }
    return render(request, 'core/user/create_review.html', context)


@login_required
@require_POST
def add_review_reply(request, review_id):
    """Add seller reply to a review"""
    review = get_object_or_404(Review, pk=review_id)
    
    if not can_reply_review(request.user, review):
        return JsonResponse({
            'success': False,
            'message': 'You do not have permission to reply to this review or have already replied.'
        })
    
    form = ReviewReplyForm(request.POST)
    if form.is_valid():
        review.seller_reply = form.cleaned_data['seller_reply']
        review.seller_replied_at = timezone.now()
        review.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Review reply sent successfully.',
            'seller_reply': review.seller_reply,
            'seller_replied_at': review.seller_replied_at.strftime('%d/%m/%Y %H:%M')
        })
    else:
        return JsonResponse({
            'success': False,
            'message': 'Invalid data.',
            'errors': form.errors
        })


def get_reviews_for_product(request, product_id):
    """Get reviews for a product (AJAX)"""
    product = get_object_or_404(Product, pk=product_id)
    reviews = Review.objects.filter(
        product=product,
        is_approved=True
    ).select_related('user', 'product__store__user').prefetch_related('media_files').order_by('-created_at')
    
    reviews_data = []
    for review in reviews:
        media_data = []
        for media in review.media_files.all():
            media_data.append({
                'media_id': media.media_id,
                'file_url': media.file.url,
                'media_type': media.media_type,
            })
        
        reviews_data.append({
            'review_id': review.review_id,
            'user_name': review.user.full_name,
            'rating': review.rating,
            'content': review.content,
            'created_at': review.created_at.strftime('%d/%m/%Y %H:%M'),
            'has_seller_reply': review.has_seller_reply,
            'seller_reply': review.seller_reply,
            'seller_replied_at': review.seller_replied_at.strftime('%d/%m/%Y %H:%M') if review.seller_replied_at else None,
            'media': media_data,
            'can_reply': can_reply_review(request.user, review) if request.user.is_authenticated else False,
        })
    
    return JsonResponse({
        'success': True,
        'reviews': reviews_data
    })


# Store Review Management Views
@login_required
def store_review_dashboard(request, store_id):
    """Store review dashboard with statistics"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    
    # Update stats
    stats = update_store_review_stats(store)
    
    # Get recent reviews since last access
    recent_reviews = get_recent_reviews_since_last_access(store)
    
    # Get negative reviews needing reply
    negative_reviews = get_negative_reviews_needing_reply(store)
    
    # Calculate order review rate (reviews / total delivered orders)
    from django.db.models import Count
    total_delivered_orders = Order.objects.filter(
        order_items__product__store=store,
        status='delivered'
    ).distinct().count()
    
    total_reviews = Review.objects.filter(
        product__store=store,
        is_approved=True
    ).count()
    
    order_review_rate = (total_reviews / total_delivered_orders * 100) if total_delivered_orders > 0 else 0
    
    # Update last accessed time
    stats.last_accessed_at = timezone.now()
    stats.save()
    
    context = {
        'store': store,
        'stats': stats,
        'recent_reviews': recent_reviews[:10],  # Limit to 10
        'negative_reviews': negative_reviews[:10],  # Limit to 10
        'order_review_rate': round(order_review_rate, 1),
        'total_reviews': total_reviews,
    }
    return render(request, 'core/store/review_dashboard.html', context)


@login_required
def store_review_list(request, store_id):
    """Store review list with filters"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    
    # Get all reviews for this store
    reviews = Review.objects.filter(
        product__store=store,
        is_approved=True
    ).select_related('user', 'product', 'order').prefetch_related('media_files').order_by('-created_at')
    
    # Apply filters
    filter_form = StoreReviewFilterForm(request.GET)
    if filter_form.is_valid():
        status = filter_form.cleaned_data.get('status')
        ratings = filter_form.cleaned_data.get('rating')
        product_name = filter_form.cleaned_data.get('product_name')
        order_id = filter_form.cleaned_data.get('order_id')
        buyer_username = filter_form.cleaned_data.get('buyer_username')
        
        if status == 'needs_reply':
            reviews = reviews.filter(seller_reply__isnull=True)
        elif status == 'replied':
            reviews = reviews.filter(seller_reply__isnull=False)
        
        if ratings:
            reviews = reviews.filter(rating__in=[int(r) for r in ratings])
        
        if product_name:
            reviews = reviews.filter(product__name__icontains=product_name)
        
        if order_id:
            reviews = reviews.filter(order__order_id=order_id)
        
        if buyer_username:
            reviews = reviews.filter(
                Q(user__full_name__icontains=buyer_username) |
                Q(user__email__icontains=buyer_username)
            )
    
    # Pagination
    paginator = Paginator(reviews, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'store': store,
        'reviews': page_obj,
        'filter_form': filter_form,
    }
    return render(request, 'core/store/review_list.html', context)


# Password Change & Reset Views
@login_required
@require_POST
def request_password_change_otp(request):
    """Request OTP for password change from profile"""
    try:
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            # Store new password in session temporarily
            request.session['new_password'] = form.cleaned_data['new_password1']
            
            # Generate and send OTP
            from otp_service.service import OTPService
            result = OTPService.generate_and_send_otp(request.user, purpose='password_reset')
            
            if result['success']:
                return JsonResponse({
                    'success': True,
                    'message': 'OTP code has been sent to your email.'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': result['message']
                })
        else:
            # Return form errors
            errors = {}
            for field, field_errors in form.errors.items():
                errors[field] = field_errors[0]
            return JsonResponse({
                'success': False,
                'message': 'Invalid data.',
                'errors': errors
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred. Please try again.'
        })


@login_required
@require_POST
def verify_password_change_otp(request):
    """Verify OTP and change password"""
    try:
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            otp_code = form.cleaned_data['otp_code']
            
            # Verify OTP
            from otp_service.service import OTPService
            result = OTPService.verify_otp(request.user.user_id, otp_code, purpose='password_reset')
            
            if result['success']:
                # Get new password from session
                new_password = request.session.get('new_password')
                if new_password:
                    # Change password
                    request.user.set_password(new_password)
                    request.user.save()
                    
                    # Clear session
                    if 'new_password' in request.session:
                        del request.session['new_password']
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Password changed successfully!'
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'message': 'Session has expired. Please try again.'
                    })
            else:
                return JsonResponse({
                    'success': False,
                    'message': result['message']
                })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Invalid OTP code.'
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred. Please try again.'
        })


def forgot_password(request):
    """Display forgot password form"""
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = CustomUser.objects.get(email=email)
                # Generate and send OTP
                from otp_service.service import OTPService
                result = OTPService.generate_and_send_otp(user, purpose='password_reset')
                
                if result['success']:
                    # Store user ID in session for verification
                    request.session['password_reset_user_id'] = user.user_id
                    return JsonResponse({
                        'success': True,
                        'message': 'OTP code has been sent to your email.'
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'message': result['message']
                    })
            except CustomUser.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Email does not exist in the system.'
                })
        else:
            errors = {}
            for field, field_errors in form.errors.items():
                errors[field] = field_errors[0]
            return JsonResponse({
                'success': False,
                'message': 'Invalid data.',
                'errors': errors
            })
    else:
        form = ForgotPasswordForm()
    
    return render(request, 'core/forgot_password.html', {'form': form})


@require_POST
def request_password_reset_otp(request):
    """Request OTP for password reset (AJAX)"""
    try:
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = CustomUser.objects.get(email=email)
            
            # Generate and send OTP
            from otp_service.service import OTPService
            result = OTPService.generate_and_send_otp(user, purpose='password_reset')
            
            if result['success']:
                # Store user ID in session for verification
                request.session['password_reset_user_id'] = user.user_id
                return JsonResponse({
                    'success': True,
                    'message': 'OTP code has been sent to your email.'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': result['message']
                })
        else:
            errors = {}
            for field, field_errors in form.errors.items():
                errors[field] = field_errors[0]
            return JsonResponse({
                'success': False,
                'message': 'Invalid data.',
                'errors': errors
            })
    except CustomUser.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Email không tồn tại trong hệ thống.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred. Please try again.'
        })


@require_POST
def verify_password_reset_otp(request):
    """Verify OTP for password reset"""
    try:
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            otp_code = form.cleaned_data['otp_code']
            user_id = request.session.get('password_reset_user_id')
            
            if not user_id:
                return JsonResponse({
                    'success': False,
                    'message': 'Phiên làm việc đã hết hạn. Vui lòng thử lại.'
                })
            
            # Verify OTP
            from otp_service.service import OTPService
            result = OTPService.verify_otp(user_id, otp_code, purpose='password_reset')
            
            if result['success']:
                return JsonResponse({
                    'success': True,
                    'message': 'OTP verified successfully. Please enter your new password.'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': result['message']
                })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Invalid OTP code.'
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred. Please try again.'
        })


@require_POST
def confirm_password_reset(request):
    """Set new password after OTP verification"""
    try:
        form = PasswordResetConfirmForm(request.POST)
        if form.is_valid():
            user_id = request.session.get('password_reset_user_id')
            
            if not user_id:
                return JsonResponse({
                    'success': False,
                    'message': 'Phiên làm việc đã hết hạn. Vui lòng thử lại.'
                })
            
            # Get user and set new password
            user = CustomUser.objects.get(user_id=user_id)
            user.set_password(form.cleaned_data['new_password1'])
            user.save()
            
            # Clear session
            if 'password_reset_user_id' in request.session:
                del request.session['password_reset_user_id']
            
            return JsonResponse({
                'success': True,
                'message': 'Password reset successfully! Please login with your new password.'
            })
        else:
            errors = {}
            for field, field_errors in form.errors.items():
                errors[field] = field_errors[0]
            return JsonResponse({
                'success': False,
                'message': 'Invalid data.',
                'errors': errors
            })
    except CustomUser.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'User does not exist.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred. Please try again.'
        })
