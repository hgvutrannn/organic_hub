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
    
    # Cart
    path('cart/', views.cart, name='cart'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('remove-from-cart/<int:cart_item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('update-cart/<int:cart_item_id>/', views.update_cart_quantity, name='update_cart_quantity'),
    
    # Orders
    path('checkout/', views.checkout, name='checkout'),
    path('orders/', views.order_list, name='orders'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    
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
    
    # Admin URLs
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-dashboard/store/<int:store_id>/', views.admin_store_detail, name='admin_store_detail'),
    path('admin-dashboard/request/<int:request_id>/', views.admin_request_detail, name='admin_request_detail'),
    path('admin-dashboard/store/<int:store_id>/approve/', views.admin_approve_store, name='admin_approve_store'),
    path('admin-dashboard/store/<int:store_id>/reject/', views.admin_reject_store, name='admin_reject_store'),
]
