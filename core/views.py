from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Max
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from .models import (
    CustomUser, Product, Category, CartItem, Order, OrderItem, 
    Review, Address, Store, ProductImage
)
from .forms import (
    CustomUserRegistrationForm, LoginForm, ProductForm, 
    AddressForm, ReviewForm, SearchForm, ProfileUpdateForm
)


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
            user = form.save()
            messages.success(request, 'Đăng ký tài khoản thành công!')
            return redirect('login')
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
    reviews = Review.objects.filter(product=product, is_approved=True).order_by('-created_at')
    
    context = {
        'product': product,
        'reviews': reviews,
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
    
    context = {
        'order': order,
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
    """Tạo cửa hàng"""
    if request.method == 'POST':
        store_name = request.POST.get('store_name')
        store_description = request.POST.get('store_description', '')
        
        if store_name:
            store = Store.objects.create(
                user=request.user,
                store_name=store_name,
                store_description=store_description,
                is_verified_status='pending'
            )
            messages.success(request, f'Đã tạo cửa hàng "{store_name}" thành công!')
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
            order.status = new_status
            order.save()
            messages.success(request, f'Đã cập nhật trạng thái đơn hàng thành "{order.get_status_display()}"')
            return redirect('store_order_detail', store_id=store.store_id, order_id=order.order_id)
    
    context = {
        'store': store,
        'order': order,
        'store_order_items': store_order_items,
        'store_subtotal': store_subtotal,
    }
    return render(request, 'core/store/store_order_detail.html', context)
