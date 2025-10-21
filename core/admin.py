from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser, Category, Address, Store, Product, CartItem, 
    Order, OrderItem, Review
)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('phone_number', 'full_name', 'email', 'is_active', 'is_staff', 'created_at')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'status', 'created_at')
    search_fields = ('phone_number', 'full_name', 'email')
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('Thông tin cá nhân', {'fields': ('full_name', 'email')}),
        ('Quyền hạn', {'fields': ('is_active', 'is_staff', 'is_superuser', 'status')}),
        ('Thời gian', {'fields': ('last_login', 'created_at')}),
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('contact_person', 'contact_phone', 'street', 'ward', 'province', 'user', 'is_default')
    list_filter = ('province', 'is_default', 'created_at')
    search_fields = ('contact_person', 'contact_phone', 'street', 'ward', 'province')
    list_select_related = ('user',)


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('store_name', 'user', 'is_verified_status', 'created_at')
    list_filter = ('is_verified_status', 'created_at')
    search_fields = ('store_name', 'store_description')
    list_select_related = ('user',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'category', 'price', 'is_active', 'view_count', 'created_at')
    list_filter = ('is_active', 'category', 'store', 'created_at')
    search_fields = ('name', 'description', 'SKU')
    list_select_related = ('store', 'category')
    readonly_fields = ('view_count', 'created_at')


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'quantity', 'total_price', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__phone_number', 'product__name')
    list_select_related = ('user', 'product')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('total_price',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'user', 'status', 'payment_status', 'total_amount', 'created_at')
    list_filter = ('status', 'payment_status', 'payment_method', 'created_at')
    search_fields = ('order_id', 'user__phone_number', 'user__full_name')
    list_select_related = ('user', 'shipping_address')
    readonly_fields = ('order_id', 'created_at', 'updated_at')
    inlines = [OrderItemInline]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'rating', 'title', 'is_approved', 'created_at')
    list_filter = ('rating', 'is_approved', 'is_verified_purchase', 'created_at')
    search_fields = ('user__phone_number', 'product__name', 'title')
    list_select_related = ('user', 'product')


