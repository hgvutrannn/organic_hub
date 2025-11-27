from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser, Category, Address, Store, Product, CartItem, 
    Order, OrderItem, Review, ProductComment, ReviewMedia, StoreReviewStats, ProductVariant,
    FlashSale, FlashSaleProduct, DiscountCode, DiscountCodeProduct, CertificationOrganization,
    StoreCertification, StoreVerificationRequest
)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'full_name', 'is_active', 'is_staff', 'created_at')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'status', 'created_at')
    search_fields = ('email', 'full_name')
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Thông tin cá nhân', {'fields': ('full_name',)}),
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


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ('variant_name', 'sku_code', 'price', 'stock', 'is_active')
    readonly_fields = ('created_at',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'category', 'price', 'has_variants', 'variants_count', 'is_active', 'view_count', 'created_at')
    list_filter = ('is_active', 'has_variants', 'category', 'store', 'created_at')
    search_fields = ('name', 'description', 'SKU')
    list_select_related = ('store', 'category')
    readonly_fields = ('view_count', 'created_at', 'variants_count_display')
    inlines = [ProductVariantInline]
    
    def variants_count(self, obj):
        """Hiển thị số lượng variants"""
        count = obj.variants.count()
        if count > 0:
            return f"{count} variants"
        return "0 variants"
    variants_count.short_description = 'Số phân loại'
    
    def variants_count_display(self, obj):
        """Hiển thị chi tiết variants trong edit form"""
        if obj.pk:
            variants = obj.variants.all()
            if variants.exists():
                html = f"<strong>Tổng số: {variants.count()}</strong><ul>"
                for v in variants:
                    status = "✓" if v.is_active else "✗"
                    html += f"<li>{status} {v.variant_name} - {v.price} VNĐ (Stock: {v.stock})</li>"
                html += "</ul>"
                return html
            return "Chưa có phân loại nào"
        return "Lưu sản phẩm trước để thêm phân loại"
    variants_count_display.short_description = 'Danh sách phân loại'
    variants_count_display.allow_tags = True
    
    def save_model(self, request, obj, form, change):
        """Tự động bật has_variants nếu có variants"""
        super().save_model(request, obj, form, change)
        # Nếu có variants nhưng has_variants=False, tự động bật
        if obj.variants.exists() and not obj.has_variants:
            obj.has_variants = True
            obj.save(update_fields=['has_variants'])


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'variant', 'quantity', 'total_price', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__email', 'user__full_name', 'product__name', 'variant__variant_name')
    list_select_related = ('user', 'product', 'variant')


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('variant_name', 'product', 'sku_code', 'price', 'stock', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('variant_name', 'sku_code', 'product__name')
    list_select_related = ('product',)
    readonly_fields = ('created_at', 'updated_at')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ('product', 'variant', 'quantity', 'unit_price', 'total_price')
    readonly_fields = ('total_price',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'user', 'status', 'payment_status', 'total_amount', 'created_at')
    list_filter = ('status', 'payment_status', 'payment_method', 'created_at')
    search_fields = ('order_id', 'user__email', 'user__full_name')
    list_select_related = ('user', 'shipping_address')
    readonly_fields = ('order_id', 'created_at', 'updated_at')
    inlines = [OrderItemInline]


class ReviewMediaInline(admin.TabularInline):
    model = ReviewMedia
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'rating', 'content_preview', 'has_seller_reply', 'is_approved', 'created_at')
    list_filter = ('rating', 'is_approved', 'is_verified_purchase', 'created_at')
    search_fields = ('user__email', 'user__full_name', 'product__name', 'content')
    list_select_related = ('user', 'product', 'order_item')
    inlines = [ReviewMediaInline]
    
    def content_preview(self, obj):
        """Preview of review content"""
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Nội dung'


@admin.register(ProductComment)
class ProductCommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'content_preview', 'has_seller_reply', 'is_approved', 'created_at')
    list_filter = ('is_approved', 'created_at')
    search_fields = ('user__email', 'user__full_name', 'product__name', 'content')
    list_select_related = ('user', 'product')
    
    def content_preview(self, obj):
        """Preview of comment content"""
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Nội dung'


@admin.register(ReviewMedia)
class ReviewMediaAdmin(admin.ModelAdmin):
    list_display = ('review', 'media_type', 'order', 'created_at')
    list_filter = ('media_type', 'created_at')
    search_fields = ('review__product__name',)
    list_select_related = ('review',)


@admin.register(StoreReviewStats)
class StoreReviewStatsAdmin(admin.ModelAdmin):
    list_display = ('store', 'avg_rating_30d', 'total_reviews_30d', 'good_reviews_count', 'negative_reviews_count', 'last_accessed_at')
    list_filter = ('last_accessed_at',)
    search_fields = ('store__store_name',)
    readonly_fields = ('total_reviews_30d', 'avg_rating_30d', 'good_reviews_count', 'negative_reviews_count', 'updated_at')


@admin.register(FlashSale)
class FlashSaleAdmin(admin.ModelAdmin):
    list_display = ('name', 'store', 'start_date', 'end_date', 'status', 'is_active', 'created_at')
    list_filter = ('status', 'is_active', 'created_at')
    search_fields = ('name', 'store__store_name')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'


@admin.register(FlashSaleProduct)
class FlashSaleProductAdmin(admin.ModelAdmin):
    list_display = ('flash_sale', 'product', 'flash_price', 'flash_stock', 'sort_order')
    list_filter = ('flash_sale', 'created_at')
    search_fields = ('product__name', 'flash_sale__name')


@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'store', 'discount_type', 'discount_value', 'scope', 'status', 'start_date', 'end_date', 'used_count', 'max_usage')
    list_filter = ('discount_type', 'scope', 'status', 'is_active', 'created_at')
    search_fields = ('code', 'name', 'store__store_name')
    readonly_fields = ('used_count', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'


@admin.register(DiscountCodeProduct)
class DiscountCodeProductAdmin(admin.ModelAdmin):
    list_display = ('discount_code', 'product', 'created_at')
    list_filter = ('discount_code', 'created_at')
    search_fields = ('product__name', 'discount_code__code')


@admin.register(CertificationOrganization)
class CertificationOrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'abbreviation', 'website', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'abbreviation', 'description')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('name', 'abbreviation', 'description')
        }),
        ('Thông tin liên hệ', {
            'fields': ('website',)
        }),
        ('Trạng thái', {
            'fields': ('is_active',)
        }),
        ('Thời gian', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(StoreCertification)
class StoreCertificationAdmin(admin.ModelAdmin):
    list_display = ('certification_id', 'verification_request', 'certification_type', 'certification_organization', 'certification_name', 'uploaded_at')
    list_filter = ('certification_type', 'certification_organization', 'uploaded_at')
    search_fields = ('certification_name', 'verification_request__store__store_name')
    readonly_fields = ('uploaded_at',)
    list_select_related = ('verification_request__store', 'certification_organization')


@admin.register(StoreVerificationRequest)
class StoreVerificationRequestAdmin(admin.ModelAdmin):
    list_display = ('request_id', 'store', 'status', 'submitted_at', 'reviewed_at', 'reviewed_by', 'certifications_count')
    list_filter = ('status', 'submitted_at', 'reviewed_at')
    search_fields = ('store__store_name', 'store__user__email', 'store__user__full_name')
    readonly_fields = ('submitted_at',)
    list_select_related = ('store', 'reviewed_by')
    
    def certifications_count(self, obj):
        return obj.certifications.count()
    certifications_count.short_description = 'Số chứng nhận'


