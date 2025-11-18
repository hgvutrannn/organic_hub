from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Max
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from .models import (
    CustomUser, Product, 
    Category, CartItem, Order, OrderItem, Review, Address, Store, 
    ProductImage, StoreCertification, StoreVerificationRequest,
    ProductComment, ReviewMedia, StoreReviewStats
)
from .forms import (
    CustomUserRegistrationForm, LoginForm, ProductForm, AddressForm, ReviewForm, SearchForm, ProfileUpdateForm,
    StoreCertificationForm, AdminStoreReviewForm, PasswordChangeForm, ForgotPasswordForm, 
    PasswordResetConfirmForm, OTPVerificationForm,
    ProductCommentForm, ProductCommentReplyForm, ReviewReplyForm, StoreReviewFilterForm
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


def can_comment_product(user, product):
    """Check if user can comment on a product"""
    if not user.is_authenticated:
        return False
    return has_user_purchased_product(user, product)


def can_reply_comment(user, comment):
    """Check if user can reply to a comment (must be shop owner)"""
    if not user.is_authenticated:
        return False
    return comment.product.store.user == user


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
    """Trang chủ - hiển thị sản phẩm nổi bật"""
    featured_products = Product.objects.filter(is_active=True).order_by('-view_count')[:8]
    
    context = {
        'featured_products': featured_products,
    }
    return render(request, 'core/home.html', context)


# Authentication Views
def register(request):
    """Đăng ký tài khoản"""
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
                messages.success(request, 'Đăng ký thành công! Vui lòng kiểm tra email để xác thực tài khoản.')
                return redirect('otp_service:verify', user_id=user.user_id)
            else:
                messages.error(request, 'Có lỗi khi gửi OTP. Vui lòng thử lại.')
    else:
        form = CustomUserRegistrationForm()
    
    return render(request, 'core/register.html', {'form': form})


def user_login(request):
    """Đăng nhập"""
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            phone_number = form.cleaned_data['phone_number']
            password = form.cleaned_data['password']
            user = authenticate(request, username=phone_number, password=password)
            
            if user is not None:
                # Check if email is verified
                if not user.email_verified:
                    messages.warning(request, 'Vui lòng xác thực email trước khi đăng nhập.')
                    return redirect('otp_service:verify', user_id=user.user_id)
                
                # Email verified, allow login
                login(request, user)
                user.last_login_at = timezone.now()
                print(user.user_id)
                user.save()
                messages.success(request, f'Chào mừng {user.full_name}!')
                return redirect('home')
            else:
                messages.error(request, 'Số điện thoại hoặc mật khẩu không đúng.')
    else:
        form = LoginForm()
    
    return render(request, 'core/login.html', {'form': form})


def user_logout(request):
    """Đăng xuất"""
    logout(request)
    messages.info(request, 'Bạn đã đăng xuất.')
    return redirect('home')


# Product Views
def product_list(request):
    """Danh sách sản phẩm"""
    products = Product.objects.filter(is_active=True)
    categories = Category.objects.all()
    
    # Search and filter
    search_form = SearchForm(request.GET)
    if search_form.is_valid():
        query = search_form.cleaned_data.get('query')
        category = search_form.cleaned_data.get('category')
        min_price = search_form.cleaned_data.get('min_price')
        max_price = search_form.cleaned_data.get('max_price')
        
        if query:
            products = products.filter(
                Q(name__icontains=query) | Q(description__icontains=query)
            )
        if category:
            products = products.filter(category=category)
        if min_price:
            products = products.filter(price__gte=min_price)
        if max_price:
            products = products.filter(price__lte=max_price)
    
    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'categories': categories,
        'search_form': search_form,
    }
    return render(request, 'core/product_list.html', context)


def product_detail(request, product_id):
    """Chi tiết sản phẩm"""
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    
    # Tăng view count
    product.view_count += 1
    product.save()
    
    # Lấy đánh giá
    reviews = Review.objects.filter(product=product, is_approved=True).select_related('user').prefetch_related('media_files').order_by('-created_at')
    
    # Check if user can comment
    can_comment = can_comment_product(request.user, product) if request.user.is_authenticated else False
    
    context = {
        'product': product,
        'reviews': reviews,
        'can_comment': can_comment,
    }
    return render(request, 'core/product_detail.html', context)


# Cart Views
@login_required
def cart(request):
    """Giỏ hàng"""
    cart_items = CartItem.objects.filter(user=request.user)
    total = sum(item.total_price for item in cart_items)
    
    context = {
        'cart_items': cart_items,
        'total': total,
    }
    return render(request, 'core/cart.html', context)


@login_required
@require_POST
def add_to_cart(request, product_id):
    """Thêm sản phẩm vào giỏ hàng"""
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    quantity = int(request.POST.get('quantity', 1))
    
    cart_item, created = CartItem.objects.get_or_create(
        user=request.user,
        product=product,
        defaults={'quantity': quantity}
    )
    
    if not created:
        cart_item.quantity += quantity
        cart_item.save()
    
    messages.success(request, f'Đã thêm {product.name} vào giỏ hàng.')
    return redirect('product_detail', product_id=product_id)


@login_required
@require_POST
def remove_from_cart(request, cart_item_id):
    """Xóa sản phẩm khỏi giỏ hàng"""
    cart_item = get_object_or_404(CartItem, pk=cart_item_id, user=request.user)
    cart_item.delete()
    messages.success(request, 'Đã xóa sản phẩm khỏi giỏ hàng.')
    return redirect('cart')


@login_required
@require_POST
def update_cart_quantity(request, cart_item_id):
    """Cập nhật số lượng trong giỏ hàng"""
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
    """Thanh toán"""
    cart_items = CartItem.objects.filter(user=request.user)
    
    if not cart_items.exists():
        messages.warning(request, 'Giỏ hàng trống.')
        return redirect('cart')
    
    addresses = Address.objects.filter(user=request.user)
    
    if request.method == 'POST':
        shipping_address_id = request.POST.get('shipping_address')
        payment_method = request.POST.get('payment_method', 'cod')
        
        if not shipping_address_id:
            messages.error(request, 'Vui lòng chọn địa chỉ giao hàng.')
            return render(request, 'core/checkout.html', {
                'cart_items': cart_items,
                'addresses': addresses,
                'total': sum(item.total_price for item in cart_items)
            })
        
        shipping_address = get_object_or_404(Address, pk=shipping_address_id, user=request.user)
        
        # Tạo đơn hàng
        subtotal = sum(item.total_price for item in cart_items)
        shipping_cost = 30000  # Phí ship cố định
        total_amount = subtotal + shipping_cost
        
        order = Order.objects.create(
            user=request.user,
            shipping_address=shipping_address,
            subtotal=subtotal,
            shipping_cost=shipping_cost,
            total_amount=total_amount,
            payment_method=payment_method
        )
        
        # Tạo order items
        for cart_item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                quantity=cart_item.quantity,
                unit_price=cart_item.product.price,
                total_price=cart_item.total_price
            )
        
        # Xóa giỏ hàng
        cart_items.delete()
        
        messages.success(request, f'Đặt hàng thành công! Mã đơn hàng: #{order.order_id}')
        return redirect('order_detail', order_id=order.order_id)
    
    context = {
        'cart_items': cart_items,
        'addresses': addresses,
        'total': sum(item.total_price for item in cart_items)
    }
    return render(request, 'core/checkout.html', context)


@login_required
def order_list(request):
    """Danh sách đơn hàng"""
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    
    context = {
        'orders': orders,
    }
    return render(request, 'core/orders.html', context)


@login_required
def order_detail(request, order_id):
    """Chi tiết đơn hàng"""
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    
    # Get reviews for order items
    order_items_with_reviews = []
    for item in order.order_items.all():
        review = Review.objects.filter(user=request.user, order_item=item).first()
        can_review = can_create_review(request.user, item) if order.status == 'delivered' else False
        order_items_with_reviews.append({
            'item': item,
            'review': review,
            'can_review': can_review,
        })
    
    context = {
        'order': order,
        'order_items_with_reviews': order_items_with_reviews,
    }
    return render(request, 'core/order_detail.html', context)




# Profile Views
@login_required
def profile(request):
    """Trang cá nhân"""
    user = request.user
    recent_orders = Order.objects.filter(user=user).order_by('-created_at')[:5]
    
    # Check if user has any stores
    user_stores = Store.objects.filter(user=user)
    has_store = user_stores.exists()
    
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cập nhật thông tin thành công!')
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
    return render(request, 'core/profile.html', context)


@login_required
def address_management(request):
    """Quản lý địa chỉ"""
    addresses = Address.objects.filter(user=request.user)
    
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            messages.success(request, 'Thêm địa chỉ thành công.')
            return redirect('address_management')
    else:
        form = AddressForm()
    
    context = {
        'addresses': addresses,
        'form': form,
    }
    return render(request, 'core/address_management.html', context)


# Store Views
@login_required
def create_store(request):
    """Tạo cửa hàng với chứng nhận"""
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
            certification_types = request.POST.getlist('certification_types')
            certification_names = request.POST.getlist('certification_names')
            
            # Debug: Print what we received
            print(f"Debug - Files received: {len(certification_files)}")
            print(f"Debug - Types received: {certification_types}")
            print(f"Debug - Names received: {certification_names}")
            print(f"Debug - POST data keys: {list(request.POST.keys())}")
            print(f"Debug - FILES data keys: {list(request.FILES.keys())}")
            
            # Create verification request
            verification_request = StoreVerificationRequest.objects.create(
                store=store,
                status='pending'
            )
            
            # Create certification records - ensure we have matching data
            if certification_files and certification_types:
                min_length = min(len(certification_files), len(certification_types))
                for i in range(min_length):
                    file = certification_files[i]
                    cert_type = certification_types[i]
                    cert_name = certification_names[i] if i < len(certification_names) else ''
                    
                    if cert_type and file:  # Only create if both type and file are provided
                        try:
                            StoreCertification.objects.create(
                                verification_request=verification_request,
                                certification_type=cert_type,
                                certification_name=cert_name,
                                document=file
                            )
                            print(f"Debug - Created certification: {cert_type} for file: {file.name}")
                        except Exception as e:
                            print(f"Debug - Error creating certification: {e}")
            else:
                print("Debug - No certification files or types received")
            
            messages.success(request, f'Đã tạo cửa hàng "{store_name}" thành công! Yêu cầu xác minh đã được gửi.')
            return redirect('store_dashboard', store_id=store.store_id)
        else:
            messages.error(request, 'Vui lòng nhập tên cửa hàng.')
    
    return render(request, 'core/store/create_store.html')


@login_required
def store_dashboard(request, store_id):
    """Dashboard cửa hàng"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    products = Product.objects.filter(store=store)
    orders = Order.objects.filter(order_items__product__store=store).distinct().order_by('-created_at')[:10]
    
    # Get verification requests
    verification_requests = store.verification_requests.all()
    latest_request = verification_requests.first()
    
    # Thống kê cơ bản
    total_products = products.count()
    total_orders = orders.count()
    total_revenue = sum(order.total_amount for order in orders if order.payment_status == 'paid')
    
    context = {
        'store': store,
        'products': products[:5],  # 5 sản phẩm gần nhất
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
    """Quản lý sản phẩm của cửa hàng"""
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
    """Thêm sản phẩm mới"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    
    # Check if store is verified
    if store.is_verified_status != 'verified':
        messages.error(request, 'Cửa hàng cần được xác minh trước khi có thể thêm sản phẩm.')
        return redirect('store_dashboard', store_id=store.store_id)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.store = store
            product.save()
            
            # Handle multiple gallery images
            gallery_images = request.FILES.getlist('gallery_images')
            for i, image in enumerate(gallery_images[:10]):  # Limit to 10 images
                ProductImage.objects.create(
                    product=product,
                    image=image,
                    alt_text=f"{product.name} - Hình {i+1}",
                    order=i
                )
            
            messages.success(request, f'Đã thêm sản phẩm "{product.name}" thành công!')
            return redirect('store_products', store_id=store.store_id)
        else:
            messages.error(request, 'Vui lòng kiểm tra lại thông tin.')
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
    """Sửa sản phẩm"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    product = get_object_or_404(Product, pk=product_id, store=store)
    # Check if store is verified
    if store.is_verified_status != 'verified':
        messages.error(request, 'Cửa hàng cần được xác minh trước khi có thể chỉnh sửa sản phẩm.')
        return redirect('store_dashboard', store_id=store.store_id)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            
            # Handle additional gallery images
            gallery_images = request.FILES.getlist('gallery_images')
            if gallery_images:
                # Get current max order
                max_order = product.images.aggregate(Max('order'))['order__max'] or -1
                
                for i, image in enumerate(gallery_images[:10]):  # Limit to 10 images
                    ProductImage.objects.create(
                        product=product,
                        image=image,
                        alt_text=f"{product.name} - Hình {max_order + i + 2}",
                        order=max_order + i + 1
                    )
            
            messages.success(request, f'Đã cập nhật sản phẩm "{product.name}" thành công!')
            return redirect('store_products', store_id=store.store_id)
        else:
            messages.error(request, 'Vui lòng kiểm tra lại thông tin.')
    else:
        form = ProductForm(instance=product)
    
    categories = Category.objects.all()
    context = {
        'store': store,
        'product': product,
        'categories': categories,
        'form': form,
    }
    return render(request, 'core/store/product_form.html', context)


@login_required
def store_orders(request, store_id):
    """Xem đơn hàng của cửa hàng"""
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
    """Chi tiết đơn hàng của cửa hàng"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    order = get_object_or_404(Order, pk=order_id)
    
    # Lấy các sản phẩm của cửa hàng trong đơn hàng
    store_order_items = order.order_items.filter(product__store=store)
    
    if not store_order_items.exists():
        messages.error(request, 'Đơn hàng này không chứa sản phẩm của cửa hàng bạn.')
        return redirect('store_orders', store_id=store.store_id)
    
    # Tính tổng tiền của cửa hàng trong đơn hàng
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
                messages.success(request, f'Đã cập nhật trạng thái đơn hàng thành "{order.get_status_display()}"')
            else:
                messages.info(request, 'Trạng thái đơn hàng không thay đổi.')
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
    """Trang trạng thái xác minh cửa hàng"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    verification_requests = store.verification_requests.all()
    
    context = {
        'store': store,
        'verification_requests': verification_requests,
    }
    return render(request, 'core/store/verification_status.html', context)


@login_required
def verification_management(request, store_id):
    """Trang quản lý xác minh cửa hàng"""
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
            certification_types = request.POST.getlist('certification_types')
            certification_names = request.POST.getlist('certification_names')
            
            if certification_files and certification_types:
                # Create new verification request
                verification_request = StoreVerificationRequest.objects.create(
                    store=store,
                    status='pending'
                )
                
                # Create certification records
                min_length = min(len(certification_files), len(certification_types))
                for i in range(min_length):
                    file = certification_files[i]
                    cert_type = certification_types[i]
                    cert_name = certification_names[i] if i < len(certification_names) else ''
                    
                    if cert_type and file:
                        try:
                            StoreCertification.objects.create(
                                verification_request=verification_request,
                                certification_type=cert_type,
                                certification_name=cert_name,
                                document=file
                            )
                        except Exception as e:
                            print(f"Error creating certification: {e}")
                
                messages.success(request, f'Đã gửi yêu cầu xác minh mới #{verification_request.request_id} thành công!')
                return redirect('verification_management', store_id=store.store_id)
            else:
                messages.error(request, 'Vui lòng tải lên ít nhất một chứng nhận.')
        else:
            messages.error(request, 'Bạn không thể gửi yêu cầu mới khi đang có yêu cầu đang chờ xem xét.')
    
    context = {
        'store': store,
        'verification_requests': verification_requests,
        'latest_request': latest_request,
        'can_send_new_request': can_send_new_request,
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
                store.verified_at = timezone.now()
                store.verified_by = request.user
                store.save()
                
                messages.success(request, f'Đã phê duyệt yêu cầu xác minh cho cửa hàng "{store.store_name}"')
            else:  # reject
                verification_request.status = 'rejected'
                verification_request.reviewed_at = timezone.now()
                verification_request.reviewed_by = request.user
                verification_request.admin_notes = admin_notes
                verification_request.save()
                
                messages.success(request, f'Đã từ chối yêu cầu xác minh cho cửa hàng "{verification_request.store.store_name}"')
            
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
    store.verified_at = timezone.now()
    store.verified_by = request.user
    store.save()
    
    # Mark all certifications as verified
    store.certifications.update(is_verified=True)
    
    messages.success(request, f'Đã phê duyệt cửa hàng "{store.store_name}"')
    return redirect('admin_store_detail', store_id=store.store_id)


@login_required
@user_passes_test(admin_required)
@require_POST
def admin_reject_store(request, store_id):
    """Reject a store with notes"""
    store = get_object_or_404(Store, store_id=store_id)
    admin_notes = request.POST.get('admin_notes', '')
    
    if not admin_notes:
        messages.error(request, 'Vui lòng nhập lý do từ chối.')
        return redirect('admin_store_detail', store_id=store.store_id)
    
    store.is_verified_status = 'rejected'
    store.admin_notes = admin_notes
    store.save()
    
    messages.success(request, f'Đã từ chối cửa hàng "{store.store_name}"')
    return redirect('admin_store_detail', store_id=store.store_id)


# Product Comment Views
@login_required
@require_POST
def add_product_comment(request, product_id):
    """Add a comment to a product"""
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    
    if not can_comment_product(request.user, product):
        return JsonResponse({
            'success': False,
            'message': 'Bạn cần mua sản phẩm này trước khi bình luận.'
        })
    
    # Get order_item for this product
    order_item = OrderItem.objects.filter(
        order__user=request.user,
        product=product,
        order__status='delivered'
    ).first()
    
    form = ProductCommentForm(request.POST, user=request.user, product=product)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.product = product
        comment.user = request.user
        comment.order_item = order_item
        comment.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Đã thêm bình luận thành công.',
            'comment_id': comment.comment_id,
            'user_name': comment.user.full_name,
            'content': comment.content,
            'created_at': comment.created_at.strftime('%d/%m/%Y %H:%M')
        })
    else:
        return JsonResponse({
            'success': False,
            'message': 'Dữ liệu không hợp lệ.',
            'errors': form.errors
        })


def get_product_comments(request, product_id):
    """Get comments for a product (AJAX)"""
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    comments = ProductComment.objects.filter(
        product=product,
        is_approved=True
    ).select_related('user', 'product__store__user').order_by('-created_at')
    
    comments_data = []
    for comment in comments:
        comments_data.append({
            'comment_id': comment.comment_id,
            'user_name': comment.user.full_name,
            'content': comment.content,
            'created_at': comment.created_at.strftime('%d/%m/%Y %H:%M'),
            'has_seller_reply': comment.has_seller_reply,
            'seller_reply': comment.seller_reply,
            'seller_replied_at': comment.seller_replied_at.strftime('%d/%m/%Y %H:%M') if comment.seller_replied_at else None,
            'can_reply': can_reply_comment(request.user, comment) if request.user.is_authenticated else False,
        })
    
    return JsonResponse({
        'success': True,
        'comments': comments_data,
        'can_comment': can_comment_product(request.user, product) if request.user.is_authenticated else False
    })


@login_required
@require_POST
def add_comment_reply(request, comment_id):
    """Add seller reply to a comment"""
    comment = get_object_or_404(ProductComment, pk=comment_id)
    
    if not can_reply_comment(request.user, comment):
        return JsonResponse({
            'success': False,
            'message': 'Bạn không có quyền phản hồi bình luận này.'
        })
    
    if comment.has_seller_reply:
        return JsonResponse({
            'success': False,
            'message': 'Bạn đã phản hồi bình luận này rồi.'
        })
    
    form = ProductCommentReplyForm(request.POST)
    if form.is_valid():
        comment.seller_reply = form.cleaned_data['seller_reply']
        comment.seller_replied_at = timezone.now()
        comment.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Đã phản hồi bình luận thành công.',
            'seller_reply': comment.seller_reply,
            'seller_replied_at': comment.seller_replied_at.strftime('%d/%m/%Y %H:%M')
        })
    else:
        return JsonResponse({
            'success': False,
            'message': 'Dữ liệu không hợp lệ.',
            'errors': form.errors
        })


# Review Views
@login_required
def create_review(request, order_id, order_item_id):
    """Create a review for an order item"""
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    order_item = get_object_or_404(OrderItem, pk=order_item_id, order=order)
    
    if not can_create_review(request.user, order_item):
        messages.error(request, 'Bạn không thể đánh giá sản phẩm này.')
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
            
            messages.success(request, 'Đã tạo đánh giá thành công!')
            return redirect('order_detail', order_id=order_id)
        else:
            messages.error(request, 'Vui lòng kiểm tra lại thông tin.')
    else:
        form = ReviewForm()
    
    context = {
        'order': order,
        'order_item': order_item,
        'form': form,
    }
    return render(request, 'core/create_review.html', context)


@login_required
@require_POST
def add_review_reply(request, review_id):
    """Add seller reply to a review"""
    review = get_object_or_404(Review, pk=review_id)
    
    if not can_reply_review(request.user, review):
        return JsonResponse({
            'success': False,
            'message': 'Bạn không có quyền phản hồi đánh giá này hoặc đã phản hồi rồi.'
        })
    
    form = ReviewReplyForm(request.POST)
    if form.is_valid():
        review.seller_reply = form.cleaned_data['seller_reply']
        review.seller_replied_at = timezone.now()
        review.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Đã phản hồi đánh giá thành công.',
            'seller_reply': review.seller_reply,
            'seller_replied_at': review.seller_replied_at.strftime('%d/%m/%Y %H:%M')
        })
    else:
        return JsonResponse({
            'success': False,
            'message': 'Dữ liệu không hợp lệ.',
            'errors': form.errors
        })


def get_reviews_for_product(request, product_id):
    """Get reviews for a product (AJAX)"""
    product = get_object_or_404(Product, pk=product_id, is_active=True)
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
                Q(user__phone_number__icontains=buyer_username)
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
                    'message': 'Mã OTP đã được gửi đến email của bạn.'
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
                'message': 'Dữ liệu không hợp lệ.',
                'errors': errors
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Có lỗi xảy ra. Vui lòng thử lại.'
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
                        'message': 'Đổi mật khẩu thành công!'
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'message': 'Phiên làm việc đã hết hạn. Vui lòng thử lại.'
                    })
            else:
                return JsonResponse({
                    'success': False,
                    'message': result['message']
                })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Mã OTP không hợp lệ.'
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Có lỗi xảy ra. Vui lòng thử lại.'
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
                        'message': 'Mã OTP đã được gửi đến email của bạn.'
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'message': result['message']
                    })
            except CustomUser.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Email không tồn tại trong hệ thống.'
                })
        else:
            errors = {}
            for field, field_errors in form.errors.items():
                errors[field] = field_errors[0]
            return JsonResponse({
                'success': False,
                'message': 'Dữ liệu không hợp lệ.',
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
                    'message': 'Mã OTP đã được gửi đến email của bạn.'
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
                'message': 'Dữ liệu không hợp lệ.',
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
            'message': 'Có lỗi xảy ra. Vui lòng thử lại.'
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
                    'message': 'Xác thực OTP thành công. Vui lòng nhập mật khẩu mới.'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': result['message']
                })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Mã OTP không hợp lệ.'
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Có lỗi xảy ra. Vui lòng thử lại.'
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
                'message': 'Đặt lại mật khẩu thành công! Vui lòng đăng nhập với mật khẩu mới.'
            })
        else:
            errors = {}
            for field, field_errors in form.errors.items():
                errors[field] = field_errors[0]
            return JsonResponse({
                'success': False,
                'message': 'Dữ liệu không hợp lệ.',
                'errors': errors
            })
    except CustomUser.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Người dùng không tồn tại.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Có lỗi xảy ra. Vui lòng thử lại.'
        })
