# Flash Sale and Discount Code Management Views
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q

from .models import Store, Product, FlashSale, FlashSaleProduct, DiscountCode, DiscountCodeProduct


# Flash Sale Management Views
@login_required
def store_flash_sale_list(request, store_id):
    """List all flash sales for a store"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    flash_sales = FlashSale.objects.filter(store=store).order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status', 'all')
    if status_filter == 'ongoing':
        flash_sales = flash_sales.filter(status='ongoing', is_active=True)
    elif status_filter == 'upcoming':
        flash_sales = flash_sales.filter(status='upcoming', is_active=True)
    elif status_filter == 'ended':
        flash_sales = flash_sales.filter(status='ended')
    
    # Pagination
    paginator = Paginator(flash_sales, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'store': store,
        'flash_sales': page_obj,
        'status_filter': status_filter,
    }
    return render(request, 'core/store/flash_sale_list.html', context)


@login_required
def store_flash_sale_create(request, store_id):
    """Create a new flash sale"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        product_ids = request.POST.getlist('products')
        
        if name and start_date and end_date:
            try:
                from datetime import datetime
                from django.utils import timezone
                # Handle datetime-local format (YYYY-MM-DDTHH:mm)
                if 'T' in start_date:
                    start_dt = datetime.strptime(start_date, '%Y-%m-%dT%H:%M')
                else:
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                if 'T' in end_date:
                    end_dt = datetime.strptime(end_date, '%Y-%m-%dT%H:%M')
                else:
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                
                # Make timezone aware
                start_dt = timezone.make_aware(start_dt)
                end_dt = timezone.make_aware(end_dt)
                
                flash_sale = FlashSale.objects.create(
                    store=store,
                    name=name,
                    description=description,
                    start_date=start_dt,
                    end_date=end_dt,
                    status='draft'
                )
                
                # Add products
                from decimal import Decimal
                for product_id in product_ids:
                    try:
                        product = Product.objects.get(product_id=product_id, store=store)
                        flash_price = request.POST.get(f'flash_price_{product_id}')
                        flash_stock = request.POST.get(f'flash_stock_{product_id}', 0)
                        
                        price_value = Decimal(flash_price) if flash_price else product.price
                        
                        FlashSaleProduct.objects.create(
                            flash_sale=flash_sale,
                            product=product,
                            flash_price=price_value,
                            flash_stock=int(flash_stock) if flash_stock else 0
                        )
                    except (Product.DoesNotExist, ValueError):
                        continue
                
                messages.success(request, 'Flash Sale created successfully!')
                return redirect('store_flash_sale_list', store_id=store.store_id)
            except Exception as e:
                messages.error(request, f'An error occurred: {str(e)}')
    
    # Get store products
    products = Product.objects.filter(store=store).order_by('-created_at')
    
    context = {
        'store': store,
        'products': products,
    }
    return render(request, 'core/store/flash_sale_form.html', context)


@login_required
def store_flash_sale_edit(request, store_id, flash_sale_id):
    """Edit an existing flash sale"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    flash_sale = get_object_or_404(FlashSale, flash_sale_id=flash_sale_id, store=store)
    
    if request.method == 'POST':
        flash_sale.name = request.POST.get('name', flash_sale.name)
        flash_sale.description = request.POST.get('description', '')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        
        if start_date:
            from datetime import datetime
            from django.utils import timezone
            if 'T' in start_date:
                start_dt = datetime.strptime(start_date, '%Y-%m-%dT%H:%M')
            else:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            flash_sale.start_date = timezone.make_aware(start_dt)
        if end_date:
            from datetime import datetime
            from django.utils import timezone
            if 'T' in end_date:
                end_dt = datetime.strptime(end_date, '%Y-%m-%dT%H:%M')
            else:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            flash_sale.end_date = timezone.make_aware(end_dt)
        
        flash_sale.save()
        
        # Update products
        product_ids = request.POST.getlist('products')
        # Remove old products not in new list
        FlashSaleProduct.objects.filter(flash_sale=flash_sale).exclude(product_id__in=product_ids).delete()
        
        # Add/update products
        from decimal import Decimal
        for product_id in product_ids:
            try:
                product = Product.objects.get(product_id=product_id, store=store)
                flash_price = request.POST.get(f'flash_price_{product_id}')
                flash_stock = request.POST.get(f'flash_stock_{product_id}', 0)
                
                price_value = Decimal(flash_price) if flash_price else product.price
                
                flash_sale_product, created = FlashSaleProduct.objects.get_or_create(
                    flash_sale=flash_sale,
                    product=product,
                    defaults={
                        'flash_price': price_value,
                        'flash_stock': int(flash_stock) if flash_stock else 0
                    }
                )
                
                if not created:
                    flash_sale_product.flash_price = price_value
                    flash_sale_product.flash_stock = int(flash_stock) if flash_stock else 0
                    flash_sale_product.save()
            except (Product.DoesNotExist, ValueError):
                continue
        
        messages.success(request, 'Flash Sale updated successfully!')
        return redirect('store_flash_sale_list', store_id=store.store_id)
    
    # Get store products and selected products
    products = Product.objects.filter(store=store).order_by('-created_at')
    selected_products = flash_sale.products.all()
    selected_product_ids = [p.product_id for p in selected_products]
    
    context = {
        'store': store,
        'flash_sale': flash_sale,
        'products': products,
        'selected_products': selected_products,
        'selected_product_ids': selected_product_ids,
    }
    return render(request, 'core/store/flash_sale_form.html', context)


@login_required
def store_flash_sale_delete(request, store_id, flash_sale_id):
    """Delete a flash sale"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    flash_sale = get_object_or_404(FlashSale, flash_sale_id=flash_sale_id, store=store)
    
    if request.method == 'POST':
        flash_sale.delete()
        messages.success(request, 'Flash Sale deleted successfully!')
        return redirect('store_flash_sale_list', store_id=store.store_id)
    
    return redirect('store_flash_sale_list', store_id=store.store_id)


# Discount Code Management Views
@login_required
def store_discount_code_list(request, store_id):
    """List all discount codes for a store"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    discount_codes = DiscountCode.objects.filter(store=store).order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status', 'all')
    if status_filter == 'active':
        discount_codes = discount_codes.filter(status='active', is_active=True)
    elif status_filter == 'upcoming':
        discount_codes = discount_codes.filter(status='draft')
    elif status_filter == 'ended':
        discount_codes = discount_codes.filter(status='ended')
    
    # Search
    search_query = request.GET.get('search', '')
    search_type = request.GET.get('search_type', 'name')
    if search_query:
        if search_type == 'name':
            discount_codes = discount_codes.filter(name__icontains=search_query)
        elif search_type == 'code':
            discount_codes = discount_codes.filter(code__icontains=search_query)
    
    # Pagination
    paginator = Paginator(discount_codes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'store': store,
        'discount_codes': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
        'search_type': search_type,
    }
    return render(request, 'core/store/discount_code_list.html', context)


@login_required
def store_discount_code_create(request, store_id):
    """Create a new discount code"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    
    if request.method == 'POST':
        code = request.POST.get('code')
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        discount_type = request.POST.get('discount_type')
        discount_value = request.POST.get('discount_value')
        max_discount_amount = request.POST.get('max_discount_amount') or None
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        max_usage = request.POST.get('max_usage', 0)
        status = request.POST.get('status', 'draft')
        
        if code and name and discount_type and discount_value and start_date and end_date:
            # Check if code already exists
            if DiscountCode.objects.filter(code=code).exists():
                messages.error(request, 'Discount code already exists!')
            else:
                try:
                    from datetime import datetime
                    from django.utils import timezone
                    # Handle datetime-local format
                    if 'T' in start_date:
                        start_dt = datetime.strptime(start_date, '%Y-%m-%dT%H:%M')
                    else:
                        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                    if 'T' in end_date:
                        end_dt = datetime.strptime(end_date, '%Y-%m-%dT%H:%M')
                    else:
                        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    
                    start_dt = timezone.make_aware(start_dt)
                    end_dt = timezone.make_aware(end_dt)
                    
                    from decimal import Decimal
                    discount_code = DiscountCode.objects.create(
                        store=store,
                        code=code.upper(),
                        name=name,
                        description=description,
                        discount_type=discount_type,
                        discount_value=Decimal(discount_value),
                        min_order_amount=Decimal('0'),  # Default to 0, field kept for backward compatibility
                        max_discount_amount=Decimal(max_discount_amount) if max_discount_amount else None,
                        start_date=start_dt,
                        end_date=end_dt,
                        max_usage=int(max_usage) if max_usage else 0,
                        status=status
                    )
                    
                    messages.success(request, 'Discount code created successfully!')
                    return redirect('store_discount_code_list', store_id=store.store_id)
                except Exception as e:
                    messages.error(request, f'An error occurred: {str(e)}')
    
    context = {
        'store': store,
    }
    return render(request, 'core/store/discount_code_form.html', context)


@login_required
def store_discount_code_edit(request, store_id, discount_code_id):
    """Edit an existing discount code"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    discount_code = get_object_or_404(DiscountCode, discount_code_id=discount_code_id, store=store)
    
    if request.method == 'POST':
        from decimal import Decimal
        discount_code.name = request.POST.get('name', discount_code.name)
        discount_code.description = request.POST.get('description', '')
        discount_code.discount_type = request.POST.get('discount_type', discount_code.discount_type)
        discount_value = request.POST.get('discount_value', discount_code.discount_value)
        discount_code.discount_value = Decimal(discount_value) if discount_value else discount_code.discount_value
        max_discount_amount = request.POST.get('max_discount_amount') or None
        discount_code.max_discount_amount = Decimal(max_discount_amount) if max_discount_amount else None
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        discount_code.max_usage = int(request.POST.get('max_usage', 0)) if request.POST.get('max_usage') else 0
        discount_code.status = request.POST.get('status', discount_code.status)
        
        if start_date:
            from datetime import datetime
            from django.utils import timezone
            if 'T' in start_date:
                start_dt = datetime.strptime(start_date, '%Y-%m-%dT%H:%M')
            else:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            discount_code.start_date = timezone.make_aware(start_dt)
        if end_date:
            from datetime import datetime
            from django.utils import timezone
            if 'T' in end_date:
                end_dt = datetime.strptime(end_date, '%Y-%m-%dT%H:%M')
            else:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            discount_code.end_date = timezone.make_aware(end_dt)
        
        discount_code.save()
        
        messages.success(request, 'Discount code updated successfully!')
        return redirect('store_discount_code_list', store_id=store.store_id)
    
    context = {
        'store': store,
        'discount_code': discount_code,
    }
    return render(request, 'core/store/discount_code_form.html', context)


@login_required
def store_discount_code_delete(request, store_id, discount_code_id):
    """Delete a discount code"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    discount_code = get_object_or_404(DiscountCode, discount_code_id=discount_code_id, store=store)
    
    if request.method == 'POST':
        discount_code.delete()
        messages.success(request, 'Discount code deleted successfully!')
        return redirect('store_discount_code_list', store_id=store.store_id)
    
    return redirect('store_discount_code_list', store_id=store.store_id)


# AJAX Views for Product Selection
@login_required
def get_store_products_ajax(request, store_id):
    """Get store products for AJAX product selection modal"""
    store = get_object_or_404(Store, store_id=store_id, user=request.user)
    products = Product.objects.filter(store=store).order_by('-created_at')
    
    search_query = request.GET.get('search', '')
    if search_query:
        products = products.filter(name__icontains=search_query)
    
    products_data = []
    for product in products:
        products_data.append({
            'product_id': product.product_id,
            'name': product.name,
            'price': float(product.price),
            'display_price': float(product.display_price),
            'image_url': product.get_primary_image.url if product.get_primary_image else None,
            'stock': product.variants.first().stock if product.has_variants and product.variants.exists() else 0,
        })
    
    return JsonResponse({
        'success': True,
        'products': products_data
    })

