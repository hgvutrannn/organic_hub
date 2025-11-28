from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from django.core.validators import RegexValidator


# Abstract Base Model with created_at and updated_at
class TimeStampedModel(models.Model):
    """Abstract base model with automatic created_at and updated_at"""
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Created At')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Updated At')
    
    class Meta:
        abstract = True


# Custom User Manager
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, full_name=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        
        user = self.model(
            email=self.normalize_email(email),
            full_name=full_name,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, full_name=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('email_verified', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, full_name, **extra_fields)


# Custom User Model
class CustomUser(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    user_id = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=100, verbose_name='Full Name')
    email = models.EmailField(max_length=255, unique=True, verbose_name='Email')
    email_verified = models.BooleanField(default=False, verbose_name='Email Verified')
    status = models.CharField(
        max_length=50,
        default='active',
        choices=[
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('blocked', 'Blocked'),
        ]
    )
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name='Avatar')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.email

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name


# Category Model
class Category(models.Model):
    category_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True, verbose_name='Category Name')
    slug = models.SlugField(max_length=255, unique=True, verbose_name='Slug')

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name


# Address Model
class Address(TimeStampedModel):
    address_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='addresses')
    street = models.CharField(max_length=255, verbose_name='Address')
    ward = models.CharField(max_length=100, verbose_name='Ward/Commune')
    province = models.CharField(max_length=100, verbose_name='Province/City')
    country = models.CharField(max_length=100, default='Vietnam', verbose_name='Country')
    contact_phone = models.CharField(max_length=20, verbose_name='Contact Phone')
    contact_person = models.CharField(max_length=100, verbose_name='Contact Person')
    is_default = models.BooleanField(default=False, verbose_name='Default Address')

    class Meta:
        verbose_name = 'Address'
        verbose_name_plural = 'Addresses'

    def __str__(self):
        return f"{self.contact_person} - {self.street}, {self.ward}, {self.province}"


# Store Model
class Store(TimeStampedModel):
    store_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='stores')
    store_name = models.CharField(max_length=255, verbose_name='Store Name')
    store_description = models.TextField(blank=True, null=True, verbose_name='Store Description')
    store_address = models.OneToOneField(Address, on_delete=models.SET_NULL, null=True, blank=True, related_name='store_of')
    is_verified_status = models.CharField(
        max_length=50, 
        default='pending', 
        choices=[
            ('pending', 'Pending'), 
            ('verified', 'Verified'), 
            ('rejected', 'Rejected')
        ],
        verbose_name='Verification Status'
    )

    class Meta:
        verbose_name = 'Store'
        verbose_name_plural = 'Stores'

    def __str__(self):
        return self.store_name
    
    @property
    def admin_notes(self):
        """Get admin notes from the latest verification request"""
        if not hasattr(self, '_admin_notes_cache'):
            latest_request = self.verification_requests.first()
            self._admin_notes_cache = latest_request.admin_notes if latest_request else None
        return self._admin_notes_cache
    
    @property
    def verified_at(self):
        """Get verification time from the most recent approved request"""
        if not hasattr(self, '_verified_at_cache'):
            approved_request = self.verification_requests.filter(
                status='approved'
            ).first()
            self._verified_at_cache = approved_request.reviewed_at if approved_request else None
        return self._verified_at_cache


# Store Verification Request Model
class StoreVerificationRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    request_id = models.AutoField(primary_key=True)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='verification_requests', verbose_name='Store')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Status'
    )
    submitted_at = models.DateTimeField(default=timezone.now, verbose_name='Submitted At')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='Reviewed At')
    reviewed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_requests',
        verbose_name='Reviewed By'
    )
    admin_notes = models.TextField(blank=True, null=True, verbose_name='Admin Notes')
    
    class Meta:
        verbose_name = 'Store Verification Request'
        verbose_name_plural = 'Store Verification Requests'
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"Request #{self.request_id} - {self.store.store_name} - {self.get_status_display()}"
    
    @property
    def certifications_count(self):
        """Get the number of certifications in this request"""
        return self.certifications.count()


# Certification Organization Model
class CertificationOrganization(TimeStampedModel):
    """Organic certification organization"""
    organization_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True, verbose_name='Organization Name')
    abbreviation = models.CharField(max_length=50, unique=True, verbose_name='Abbreviation')
    description = models.TextField(blank=True, null=True, verbose_name='Description')
    website = models.URLField(blank=True, null=True, verbose_name='Website')
    is_active = models.BooleanField(default=True, verbose_name='Active')
    
    class Meta:
        verbose_name = 'Certification Organization'
        verbose_name_plural = 'Certification Organizations'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.abbreviation})"


# Store Certification Model
class StoreCertification(models.Model):
    certification_id = models.AutoField(primary_key=True)
    verification_request = models.ForeignKey(StoreVerificationRequest, on_delete=models.CASCADE, related_name='certifications', verbose_name='Verification Request', null=True, blank=True)
    certification_organization = models.ForeignKey(
        CertificationOrganization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='certifications',
        verbose_name='Certification Organization'
    )
    certificate_number = models.CharField(max_length=255, blank=True, null=True, verbose_name='Certificate Number')
    issue_date = models.DateField(null=True, blank=True, verbose_name='Issue Date')
    expiry_date = models.DateField(null=True, blank=True, verbose_name='Expiry Date')
    document = models.FileField(upload_to='certifications/', verbose_name='Certificate Document')
    uploaded_at = models.DateTimeField(default=timezone.now, verbose_name='Uploaded At')
    
    class Meta:
        verbose_name = 'Store Certification'
        verbose_name_plural = 'Store Certifications'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        org_name = self.certification_organization.name if self.certification_organization else "Unknown"
        store_name = self.verification_request.store.store_name if self.verification_request and self.verification_request.store else "Unknown"
        return f"{store_name} - {org_name}"
    
    @property
    def file_extension(self):
        """Get file extension for display purposes"""
        if self.document:
            return self.document.name.split('.')[-1].lower()
        return None
    
    @property
    def is_image(self):
        """Check if the uploaded file is an image"""
        image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
        return self.file_extension in image_extensions

# Legacy Product Model (for backward compatibility during migration)
class Product(TimeStampedModel):
    product_id = models.AutoField(primary_key=True)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products', verbose_name='Store')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products', verbose_name='Category')
    name = models.CharField(max_length=255, verbose_name='Product Name')
    description = models.TextField(blank=True, null=True, verbose_name='Description')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Price')
    base_unit = models.CharField(max_length=50, blank=True, null=True, verbose_name='Unit')
    stock = models.IntegerField(default=0, verbose_name='Stock Quantity', help_text='Only applies to products without variants')
    SKU = models.CharField(max_length=255, unique=True, blank=True, null=True, verbose_name='SKU Code')
    view_count = models.PositiveIntegerField(default=0, verbose_name='View Count')
    
    # Variant support fields
    has_variants = models.BooleanField(default=False, verbose_name='Has Variants')

    class Meta:
        verbose_name = 'Product'
        verbose_name_plural = 'Products'

    def __str__(self):
        return self.name
    
    def get_images(self, primary_only=False):
        """
        Get product images
        
        Args:
            primary_only (bool): If True, returns only the primary image (order=0). 
                                If False, returns all images in order.
        
        Returns:
            - If primary_only=True: Returns ProductImage object or None
            - If primary_only=False: Returns QuerySet of ProductImage
        """
        if primary_only:
            # Return primary image (order=0) or first image
            primary_image = self.images.filter(order=0).first() or self.images.first()
            return primary_image
        else:
            # Return all images in order
            return self.images.all().order_by('order', 'created_at')
    
    @property
    def get_primary_image(self):
        """
        Property for backward compatibility - returns primary image (ImageField object)
        Use get_images(primary_only=True) instead
        """
        primary_image = self.get_images(primary_only=True)
        if primary_image:
            return primary_image.image
        return None
    
    @property
    def min_price(self):
        """Get minimum price from variants or product price"""
        if self.has_variants and self.variants.exists():
            return min(v.price for v in self.variants.filter(is_active=True))
        return self.price
    
    @property
    def max_price(self):
        """Get maximum price from variants or product price"""
        if self.has_variants and self.variants.exists():
            return max(v.price for v in self.variants.filter(is_active=True))
        return self.price
    
    @property
    def display_price(self):
        """Get display price: minimum variant price if has variants, otherwise product price"""
        if self.has_variants and self.variants.exists():
            active_variants = self.variants.filter(is_active=True)
            if active_variants.exists():
                return min(v.price for v in active_variants)
        return self.price
    
    @property
    def default_variant(self):
        """Get default variant (first variant or variant with lowest price)"""
        if self.has_variants and self.variants.exists():
            return self.variants.filter(is_active=True).order_by('price', 'created_at').first()
        return None


class ProductImage(TimeStampedModel):
    product_image_id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images', verbose_name='Product')
    image = models.ImageField(upload_to='products/gallery/', verbose_name='Image')
    alt_text = models.CharField(max_length=255, blank=True, null=True, verbose_name='Alt Text')
    order = models.PositiveIntegerField(default=0, verbose_name='Order', help_text='Image with order=0 will be the primary image')

    class Meta:
        verbose_name = 'Product Image'
        verbose_name_plural = 'Product Images'
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.product.name} - {self.alt_text or 'Image'}"


# Product Variant Model (SKU)
class ProductVariant(TimeStampedModel):
    variant_id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants', verbose_name='Product')
    variant_name = models.CharField(max_length=255, verbose_name='Variant Name', help_text='e.g., 500g, 1kg, Size M - Red')
    variant_description = models.TextField(blank=True, null=True, verbose_name='Variant Description')
    sku_code = models.CharField(max_length=255, unique=True, blank=True, null=True, verbose_name='SKU Code')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Price')
    stock = models.IntegerField(default=0, verbose_name='Stock Quantity')
    image = models.ImageField(upload_to='products/variants/', null=True, blank=True, verbose_name='Variant Image')
    is_active = models.BooleanField(default=True, verbose_name='Active')

    class Meta:
        verbose_name = 'Product Variant'
        verbose_name_plural = 'Product Variants'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.product.name} - {self.variant_name}"
    
    def save(self, *args, **kwargs):
        """Automatically enable has_variants for product when creating variant"""
        super().save(*args, **kwargs)
        # Automatically enable has_variants if not already enabled
        if not self.product.has_variants:
            self.product.has_variants = True
            self.product.save(update_fields=['has_variants'])
    
    def delete(self, *args, **kwargs):
        """Automatically disable has_variants if no variants remain"""
        product = self.product
        super().delete(*args, **kwargs)
        # If no variants remain, disable has_variants
        if not product.variants.exists():
            product.has_variants = False
            product.save(update_fields=['has_variants'])
    
    @property
    def display_image(self):
        """Get variant image or default product image"""
        if self.image:
            return self.image
        return self.product.get_primary_image
    
    @property
    def is_in_stock(self):
        """Check if in stock"""
        return self.stock > 0


# Cart Item Model
class CartItem(TimeStampedModel):
    cart_item_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='cart_items', verbose_name='User')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='cart_items', verbose_name='Product')
    variant = models.ForeignKey('ProductVariant', on_delete=models.CASCADE, related_name='cart_items', null=True, blank=True, verbose_name='Variant')
    quantity = models.IntegerField(default=1, verbose_name='Quantity')

    class Meta:
        verbose_name = 'Cart Item'
        verbose_name_plural = 'Cart Items'
        unique_together = ('user', 'product', 'variant')

    def __str__(self):
        variant_str = f" - {self.variant.variant_name}" if self.variant else ""
        return f"{self.quantity} x {self.product.name}{variant_str} by {self.user.email}"
    
    @property
    def total_price(self):
        """Calculate total price based on variant or product"""
        price = self.variant.price if self.variant else self.product.price
        return price * self.quantity
    
    @property
    def unit_price(self):
        """Get unit price"""
        return self.variant.price if self.variant else self.product.price


# Order Model
class Order(TimeStampedModel):
    STATUS_CHOICES = [
        ('pending', 'Pending Confirmation'),
        ('waiting_pickup', 'Waiting for Pickup'),
        ('shipping', 'Shipping'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('cod', 'Cash on Delivery (COD)'),
        ('bank_transfer', 'Bank Transfer'),
        ('credit_card', 'Credit Card'),
        ('vnpay', 'VnPay'),
        ('zalopay', 'ZaloPay'),
    ]

    order_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='orders', verbose_name='User')
    shipping_address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders', verbose_name='Shipping Address')
    
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending', verbose_name='Order Status')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Subtotal')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Discount Amount')
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Shipping Cost')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Total Amount')
    
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES, default='cod', verbose_name='Payment Method')
    payment_status = models.CharField(
        max_length=50, 
        default='pending', 
        choices=[
            ('pending', 'Pending'),
            ('paid', 'Paid'),
            ('failed', 'Payment Failed'),
            ('refunded', 'Refunded'),
        ], 
        verbose_name='Payment Status'
    )
    
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='Paid At')
    notes = models.TextField(blank=True, null=True, verbose_name='Notes')
    
    class Meta:
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Order #{self.order_id} - {self.user.email} - {self.get_status_display()}"


# Order Item Model
class OrderItem(models.Model):
    order_item_id = models.AutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items', verbose_name='Order')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='order_items', verbose_name='Product')
    variant = models.ForeignKey('ProductVariant', on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items', verbose_name='Variant')
    quantity = models.IntegerField(verbose_name='Quantity')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Unit Price')
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Total Price')
    
    class Meta:
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'
    
    def __str__(self):
        variant_str = f" - {self.variant.variant_name}" if self.variant else ""
        return f"{self.quantity} x {self.product.name}{variant_str} in order #{self.order.order_id}"
    
    def save(self, *args, **kwargs):
        # If unit_price is not set, get from variant or product
        if not self.unit_price:
            if self.variant:
                self.unit_price = self.variant.price
            else:
                self.unit_price = self.product.price
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)


# Review Model
class Review(TimeStampedModel):
    review_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='reviews', verbose_name='User')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews', verbose_name='Product')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='reviews', verbose_name='Order', null=True, blank=True)
    order_item = models.ForeignKey('OrderItem', on_delete=models.CASCADE, related_name='reviews', verbose_name='Order Item', null=True, blank=True)
    
    rating = models.IntegerField(verbose_name='Rating', choices=[
        (1, '1 star'),
        (2, '2 stars'),
        (3, '3 stars'),
        (4, '4 stars'),
        (5, '5 stars'),
    ])
    content = models.TextField(verbose_name='Review Content')
    
    seller_reply = models.TextField(blank=True, null=True, verbose_name='Seller Reply')
    seller_replied_at = models.DateTimeField(null=True, blank=True, verbose_name='Replied At')
    
    is_verified_purchase = models.BooleanField(default=True, verbose_name='Verified Purchase')
    is_approved = models.BooleanField(default=True, verbose_name='Approved')
    
    class Meta:
        verbose_name = 'Product Review'
        verbose_name_plural = 'Product Reviews'
        unique_together = ('user', 'order_item')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.rating} star review for {self.product.name} by {self.user.email}"
    
    @property
    def has_seller_reply(self):
        """Check if review has seller reply"""
        return bool(self.seller_reply)


# Review Media Model
class ReviewMedia(TimeStampedModel):
    MEDIA_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
    ]
    
    media_id = models.AutoField(primary_key=True)
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='media_files', verbose_name='Review')
    file = models.FileField(upload_to='reviews/media/', verbose_name='File')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, verbose_name='Media Type')
    order = models.PositiveIntegerField(default=0, verbose_name='Order')
    
    class Meta:
        verbose_name = 'Review Media'
        verbose_name_plural = 'Review Media'
        ordering = ['order', 'created_at']
    
    def __str__(self):
        return f"{self.get_media_type_display()} cho review #{self.review.review_id}"


# Product Comment Model
# Store Review Stats Model - Cached statistics
class StoreReviewStats(TimeStampedModel):
    store = models.OneToOneField(Store, on_delete=models.CASCADE, related_name='review_stats', verbose_name='Store')
    last_accessed_at = models.DateTimeField(null=True, blank=True, verbose_name='Last Accessed At')
    total_reviews_30d = models.IntegerField(default=0, verbose_name='Total Reviews (30 days)')
    avg_rating_30d = models.DecimalField(max_digits=3, decimal_places=2, default=0.00, verbose_name='Average Rating (30 days)')
    good_reviews_count = models.IntegerField(default=0, verbose_name='Good Reviews Count (4-5 stars)')
    negative_reviews_count = models.IntegerField(default=0, verbose_name='Negative Reviews Count (1-2 stars)')
    
    class Meta:
        verbose_name = 'Store Review Statistics'
        verbose_name_plural = 'Store Review Statistics'
    
    def __str__(self):
        return f"Review statistics for {self.store.store_name}"


# Flash Sale Model
class FlashSale(TimeStampedModel):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('upcoming', 'Upcoming'),
        ('ongoing', 'Ongoing'),
        ('ended', 'Ended'),
    ]
    
    flash_sale_id = models.AutoField(primary_key=True)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='flash_sales', verbose_name='Store')
    name = models.CharField(max_length=255, verbose_name='Flash Sale Name')
    description = models.TextField(blank=True, null=True, verbose_name='Description')
    start_date = models.DateTimeField(verbose_name='Start Date')
    end_date = models.DateTimeField(verbose_name='End Date')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='Status')
    is_active = models.BooleanField(default=True, verbose_name='Active')
    
    class Meta:
        verbose_name = 'Flash Sale'
        verbose_name_plural = 'Flash Sales'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.store.store_name}"
    
    @property
    def is_ongoing(self):
        """Check if flash sale is currently ongoing"""
        now = timezone.now()
        return self.start_date <= now <= self.end_date and self.is_active
    
    @property
    def is_upcoming(self):
        """Check if flash sale is upcoming"""
        now = timezone.now()
        return now < self.start_date and self.is_active
    
    @property
    def is_ended(self):
        """Check if flash sale has ended"""
        now = timezone.now()
        return now > self.end_date or not self.is_active


# Flash Sale Product Model
class FlashSaleProduct(TimeStampedModel):
    flash_sale_product_id = models.AutoField(primary_key=True)
    flash_sale = models.ForeignKey(FlashSale, on_delete=models.CASCADE, related_name='products', verbose_name='Flash Sale')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='flash_sales', verbose_name='Product')
    flash_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Flash Sale Price')
    flash_stock = models.IntegerField(default=0, verbose_name='Flash Sale Stock')
    
    class Meta:
        verbose_name = 'Flash Sale Product'
        verbose_name_plural = 'Flash Sale Products'
        unique_together = ('flash_sale', 'product')
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.product.name} - {self.flash_sale.name}"


# Discount Code Model
class DiscountCode(TimeStampedModel):
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage (%)'),
        ('fixed', 'Fixed Amount (GBP)'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('ended', 'Ended'),
    ]
    
    discount_code_id = models.AutoField(primary_key=True)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='discount_codes', verbose_name='Store')
    code = models.CharField(max_length=50, unique=True, verbose_name='Discount Code')
    name = models.CharField(max_length=255, verbose_name='Discount Code Name')
    description = models.TextField(blank=True, null=True, verbose_name='Description')
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES, verbose_name='Discount Type')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Discount Value')
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Minimum Order Amount')
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Maximum Discount')
    start_date = models.DateTimeField(verbose_name='Start Date')
    end_date = models.DateTimeField(verbose_name='End Date')
    max_usage = models.IntegerField(default=0, verbose_name='Maximum Usage (0 = unlimited)')
    used_count = models.IntegerField(default=0, verbose_name='Used Count')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='Status')
    is_active = models.BooleanField(default=True, verbose_name='Active')
    
    class Meta:
        verbose_name = 'Discount Code'
        verbose_name_plural = 'Discount Codes'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.code} - {self.store.store_name}"
    
    @property
    def is_ongoing(self):
        """Check if discount code is currently active"""
        now = timezone.now()
        return (self.start_date <= now <= self.end_date and 
                self.is_active and 
                self.status == 'active' and
                (self.max_usage == 0 or self.used_count < self.max_usage))
    
    def calculate_discount(self, order_amount):
        """Calculate discount amount for given order amount"""
        if order_amount < self.min_order_amount:
            return 0
        
        if self.discount_type == 'percentage':
            discount = order_amount * (self.discount_value / 100)
            if self.max_discount_amount:
                discount = min(discount, self.max_discount_amount)
        else:
            discount = min(self.discount_value, order_amount)
        
        return discount


# Discount Code Product Model
class DiscountCodeProduct(TimeStampedModel):
    discount_code_product_id = models.AutoField(primary_key=True)
    discount_code = models.ForeignKey(DiscountCode, on_delete=models.CASCADE, related_name='products', verbose_name='Discount Code')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='discount_codes', verbose_name='Product')
    
    class Meta:
        verbose_name = 'Discount Code Product'
        verbose_name_plural = 'Discount Code Products'
        unique_together = ('discount_code', 'product')
    
    def __str__(self):
        return f"{self.product.name} - {self.discount_code.code}"


