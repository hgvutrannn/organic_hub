from django.urls import path
from . import views

urlpatterns = [
    # Home
    path('', views.home, name='home'),
    
    # Authentication
    path('login/', views.user_login, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.user_logout, name='logout'),
    
    # Products
    path('products/', views.product_list, name='product_list'),
    path('products/<int:product_id>/', views.product_detail, name='product_detail'),
    
    # Product Variants
    path('products/<int:product_id>/variants/', views.get_product_variants, name='get_product_variants'),
    path('variants/<int:variant_id>/info/', views.get_variant_info, name='get_variant_info'),
    
    
    # Cart
    path('cart/', views.cart, name='cart'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('remove-from-cart/<int:cart_item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('update-cart/<int:cart_item_id>/', views.update_cart_quantity, name='update_cart_quantity'),
    
    # Orders
    path('checkout/', views.checkout, name='checkout'),
    path('orders/', views.order_list, name='orders'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    
    # Reviews
    path('orders/<int:order_id>/review/<int:order_item_id>/', views.create_review, name='create_review'),
    path('reviews/<int:review_id>/reply/', views.add_review_reply, name='add_review_reply'),
    path('products/<int:product_id>/reviews/', views.get_reviews_for_product, name='get_reviews_for_product'),
    
    # Profile
    path('profile/', views.profile, name='profile'),
    path('addresses/', views.address_management, name='address_management'),
    
    # Store Management
    path('create-store/', views.create_store, name='create_store'),
    path('store/<int:store_id>/', views.store_dashboard, name='store_dashboard'),
    path('store/<int:store_id>/products/', views.store_products, name='store_products'),
    path('store/<int:store_id>/products/add/', views.add_product, name='add_product'),
    path('store/<int:store_id>/products/<int:product_id>/edit/', views.edit_product, name='edit_product'),
    path('store/<int:store_id>/orders/', views.store_orders, name='store_orders'),
    path('store/<int:store_id>/orders/<int:order_id>/', views.store_order_detail, name='store_order_detail'),
    path('store/<int:store_id>/verification/', views.verification_status, name='verification_status'),
    path('store/<int:store_id>/verification/management/', views.verification_management, name='verification_management'),
    path('store/<int:store_id>/reviews/', views.store_review_dashboard, name='store_review_dashboard'),
    path('store/<int:store_id>/reviews/list/', views.store_review_list, name='store_review_list'),
    
    # Marketing Channel - Flash Sale
    path('store/<int:store_id>/flash-sale/', views.store_flash_sale_list, name='store_flash_sale_list'),
    path('store/<int:store_id>/flash-sale/create/', views.store_flash_sale_create, name='store_flash_sale_create'),
    path('store/<int:store_id>/flash-sale/<int:flash_sale_id>/edit/', views.store_flash_sale_edit, name='store_flash_sale_edit'),
    path('store/<int:store_id>/flash-sale/<int:flash_sale_id>/delete/', views.store_flash_sale_delete, name='store_flash_sale_delete'),
    
    # Marketing Channel - Discount Code
    path('store/<int:store_id>/discount-code/', views.store_discount_code_list, name='store_discount_code_list'),
    path('store/<int:store_id>/discount-code/create/', views.store_discount_code_create, name='store_discount_code_create'),
    path('store/<int:store_id>/discount-code/<int:discount_code_id>/edit/', views.store_discount_code_edit, name='store_discount_code_edit'),
    path('store/<int:store_id>/discount-code/<int:discount_code_id>/delete/', views.store_discount_code_delete, name='store_discount_code_delete'),
    
    # AJAX - Get store products for selection
    path('store/<int:store_id>/products/ajax/', views.get_store_products_ajax, name='get_store_products_ajax'),
    
    # API - Get store discount codes for cart
    path('api/store/<int:store_id>/discount-codes/', views.get_store_discount_codes, name='get_store_discount_codes'),
    
    # Admin URLs
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-dashboard/store/<int:store_id>/', views.admin_store_detail, name='admin_store_detail'),
    path('admin-dashboard/request/<int:request_id>/', views.admin_request_detail, name='admin_request_detail'),
    path('admin-dashboard/store/<int:store_id>/approve/', views.admin_approve_store, name='admin_approve_store'),
    path('admin-dashboard/store/<int:store_id>/reject/', views.admin_reject_store, name='admin_reject_store'),
    
    # Admin Category Management URLs
    path('admin-dashboard/categories/', views.admin_category_list, name='admin_category_list'),
    path('admin-dashboard/categories/create/', views.admin_category_create, name='admin_category_create'),
    path('admin-dashboard/categories/<int:category_id>/edit/', views.admin_category_edit, name='admin_category_edit'),
    path('admin-dashboard/categories/<int:category_id>/delete/', views.admin_category_delete, name='admin_category_delete'),
    
    # Admin Certification Organization Management URLs
    path('admin-dashboard/certification-organizations/', views.admin_certification_organization_list, name='admin_certification_organization_list'),
    path('admin-dashboard/certification-organizations/create/', views.admin_certification_organization_create, name='admin_certification_organization_create'),
    path('admin-dashboard/certification-organizations/<int:organization_id>/edit/', views.admin_certification_organization_edit, name='admin_certification_organization_edit'),
    path('admin-dashboard/certification-organizations/<int:organization_id>/delete/', views.admin_certification_organization_delete, name='admin_certification_organization_delete'),
    
    # Password Change & Reset URLs
    path('password/change/request-otp/', views.request_password_change_otp, name='request_password_change_otp'),
    path('password/change/verify-otp/', views.verify_password_change_otp, name='verify_password_change_otp'),
    path('password/forgot/', views.forgot_password, name='forgot_password'),
    path('password/reset/request-otp/', views.request_password_reset_otp, name='request_password_reset_otp'),
    path('password/reset/verify-otp/', views.verify_password_reset_otp, name='verify_password_reset_otp'),
    path('password/reset/confirm/', views.confirm_password_reset, name='confirm_password_reset'),
]
