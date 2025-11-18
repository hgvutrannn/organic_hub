from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from django.core.validators import RegexValidator


# Custom User Manager
class CustomUserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, email=None, full_name=None, **extra_fields):
        if not phone_number:
            raise ValueError('Số điện thoại là bắt buộc')
        if not email:
            raise ValueError('Email là bắt buộc')
        
        user = self.model(
            phone_number=phone_number,
            email=self.normalize_email(email),
            full_name=full_name,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, email=None, full_name=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('email_verified', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(phone_number, password, email, full_name, **extra_fields)


# Custom User Model
class CustomUser(AbstractBaseUser, PermissionsMixin):
    user_id = models.AutoField(primary_key=True)
    phone_number = models.CharField(
        max_length=20,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Số điện thoại phải theo định dạng: '+999999999'. Tối đa 15 chữ số."
            )
        ],
        verbose_name='Số điện thoại'
    )
    full_name = models.CharField(max_length=100, verbose_name='Họ và tên')
    email = models.EmailField(max_length=255, unique=True, null=True, blank=True)
    email_verified = models.BooleanField(default=False, verbose_name='Email đã xác thực')
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(
        max_length=50,
        default='active',
        choices=[
            ('active', 'Hoạt động'),
            ('inactive', 'Không hoạt động'),
            ('blocked', 'Bị chặn'),
        ]
    )
    last_login_at = models.DateTimeField(null=True, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name='Ảnh đại diện')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['full_name', 'email']

    class Meta:
        verbose_name = 'Người dùng'
        verbose_name_plural = 'Người dùng'

    def __str__(self):
        return self.phone_number

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name


# Category Model
class Category(models.Model):
    category_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True, verbose_name='Tên danh mục')
    slug = models.SlugField(max_length=255, unique=True, verbose_name='Slug')

    class Meta:
        verbose_name = 'Danh mục'
        verbose_name_plural = 'Danh mục'

    def __str__(self):
        return self.name


# Address Model
class Address(models.Model):
    address_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='addresses')
    street = models.CharField(max_length=255, verbose_name='Địa chỉ')
    ward = models.CharField(max_length=100, verbose_name='Phường/Xã')
    province = models.CharField(max_length=100, verbose_name='Tỉnh/Thành phố')
    country = models.CharField(max_length=100, default='Vietnam', verbose_name='Quốc gia')
    contact_phone = models.CharField(max_length=20, verbose_name='Số điện thoại liên hệ')
    contact_person = models.CharField(max_length=100, verbose_name='Người liên hệ')
    is_default = models.BooleanField(default=False, verbose_name='Địa chỉ mặc định')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Địa chỉ'
        verbose_name_plural = 'Địa chỉ'

    def __str__(self):
        return f"{self.contact_person} - {self.street}, {self.ward}, {self.province}"


# Store Model
class Store(models.Model):
    store_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='stores')
    store_name = models.CharField(max_length=255, verbose_name='Tên cửa hàng')
    store_description = models.TextField(blank=True, null=True, verbose_name='Mô tả cửa hàng')
    store_address = models.OneToOneField(Address, on_delete=models.SET_NULL, null=True, blank=True, related_name='store_of')
    created_at = models.DateTimeField(default=timezone.now)
    is_verified_status = models.CharField(
        max_length=50, 
        default='pending', 
        choices=[
            ('pending', 'Đang chờ'), 
            ('verified', 'Đã xác minh'), 
            ('rejected', 'Bị từ chối')
        ],
        verbose_name='Trạng thái xác minh'
    )
    admin_notes = models.TextField(blank=True, null=True, verbose_name='Ghi chú của admin')
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian xác minh')
    verified_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='verified_stores',
        verbose_name='Xác minh bởi'
    )

    class Meta:
        verbose_name = 'Cửa hàng'
        verbose_name_plural = 'Cửa hàng'

    def __str__(self):
        return self.store_name


# Store Verification Request Model
class StoreVerificationRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Đang chờ xem xét'),
        ('approved', 'Đã phê duyệt'),
        ('rejected', 'Bị từ chối'),
    ]
    
    request_id = models.AutoField(primary_key=True)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='verification_requests', verbose_name='Cửa hàng')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Trạng thái'
    )
    submitted_at = models.DateTimeField(default=timezone.now, verbose_name='Ngày gửi')
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name='Ngày xem xét')
    reviewed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_requests',
        verbose_name='Người xem xét'
    )
    admin_notes = models.TextField(blank=True, null=True, verbose_name='Ghi chú của admin')
    
    class Meta:
        verbose_name = 'Yêu cầu xác minh cửa hàng'
        verbose_name_plural = 'Yêu cầu xác minh cửa hàng'
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"Request #{self.request_id} - {self.store.store_name} - {self.get_status_display()}"
    
    @property
    def certifications_count(self):
        """Get the number of certifications in this request"""
        return self.certifications.count()


# Store Certification Model
class StoreCertification(models.Model):
    CERTIFICATION_TYPES = [
        ('vietgap', 'VietGAP'),
        ('organic', 'Chứng nhận hữu cơ'),
        ('fairtrade', 'Fair Trade'),
        ('halal', 'Halal'),
        ('kosher', 'Kosher'),
        ('other', 'Chứng nhận khác'),
    ]
    
    certification_id = models.AutoField(primary_key=True)
    verification_request = models.ForeignKey(StoreVerificationRequest, on_delete=models.CASCADE, related_name='certifications', verbose_name='Yêu cầu xác minh', null=True, blank=True)
    certification_type = models.CharField(
        max_length=50, 
        choices=CERTIFICATION_TYPES, 
        verbose_name='Loại chứng nhận'
    )
    certification_name = models.CharField(max_length=255, blank=True, null=True, verbose_name='Tên chứng nhận')
    document = models.FileField(upload_to='certifications/', verbose_name='Tài liệu chứng nhận')
    uploaded_at = models.DateTimeField(default=timezone.now, verbose_name='Ngày tải lên')
    
    class Meta:
        verbose_name = 'Chứng nhận cửa hàng'
        verbose_name_plural = 'Chứng nhận cửa hàng'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.verification_request.store.store_name} - {self.get_certification_type_display()}"
    
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
class Product(models.Model):
    product_id = models.AutoField(primary_key=True)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='products', verbose_name='Cửa hàng')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products', verbose_name='Danh mục')
    name = models.CharField(max_length=255, verbose_name='Tên sản phẩm')
    description = models.TextField(blank=True, null=True, verbose_name='Mô tả')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Giá')
    base_unit = models.CharField(max_length=50, verbose_name='Đơn vị')
    SKU = models.CharField(max_length=255, unique=True, blank=True, null=True, verbose_name='Mã SKU')
    is_active = models.BooleanField(default=True, verbose_name='Đang hoạt động')
    image = models.ImageField(upload_to='products/', null=True, blank=True, verbose_name='Ảnh sản phẩm chính')
    view_count = models.PositiveIntegerField(default=0, verbose_name='Số lượt xem')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Ngày tạo')
    
    # Variant support fields
    has_variants = models.BooleanField(default=False, verbose_name='Có phân loại')

    class Meta:
        verbose_name = 'Sản phẩm'
        verbose_name_plural = 'Sản phẩm'

    def __str__(self):
        return self.name
    
    @property
    def get_primary_image(self):
        """Lấy ảnh chính hoặc ảnh đầu tiên"""
        if self.image:
            return self.image
        first_image = self.images.first()
        if first_image:
            return first_image.image
        return None
    
    @property
    def min_price(self):
        """Lấy giá thấp nhất từ variants hoặc giá sản phẩm"""
        if self.has_variants and self.variants.exists():
            return min(v.price for v in self.variants.filter(is_active=True))
        return self.price
    
    @property
    def max_price(self):
        """Lấy giá cao nhất từ variants hoặc giá sản phẩm"""
        if self.has_variants and self.variants.exists():
            return max(v.price for v in self.variants.filter(is_active=True))
        return self.price
    
    @property
    def default_variant(self):
        """Lấy variant mặc định (variant đầu tiên hoặc variant có giá thấp nhất)"""
        if self.has_variants and self.variants.exists():
            return self.variants.filter(is_active=True).order_by('sort_order', 'price').first()
        return None


class ProductImage(models.Model):
    product_image_id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images', verbose_name='Sản phẩm')
    image = models.ImageField(upload_to='products/gallery/', verbose_name='Hình ảnh')
    alt_text = models.CharField(max_length=255, blank=True, null=True, verbose_name='Mô tả ảnh')
    is_primary = models.BooleanField(default=False, verbose_name='Ảnh chính')
    order = models.PositiveIntegerField(default=0, verbose_name='Thứ tự')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Ngày tạo')

    class Meta:
        verbose_name = 'Hình ảnh sản phẩm'
        verbose_name_plural = 'Hình ảnh sản phẩm'
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.product.name} - {self.alt_text or 'Image'}"


# Product Variant Model (SKU)
class ProductVariant(models.Model):
    variant_id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants', verbose_name='Sản phẩm')
    variant_name = models.CharField(max_length=255, verbose_name='Tên phân loại', help_text='Ví dụ: 500g, 1kg, Size M - Màu Đỏ')
    variant_description = models.TextField(blank=True, null=True, verbose_name='Mô tả phân loại')
    sku_code = models.CharField(max_length=255, unique=True, blank=True, null=True, verbose_name='Mã SKU')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Giá')
    stock = models.IntegerField(default=0, verbose_name='Số lượng tồn kho')
    image = models.ImageField(upload_to='products/variants/', null=True, blank=True, verbose_name='Hình ảnh phân loại')
    attributes = models.JSONField(blank=True, null=True, verbose_name='Thuộc tính', help_text='Ví dụ: {"Size": "M", "Color": "Đỏ"}')
    is_active = models.BooleanField(default=True, verbose_name='Đang hoạt động')
    sort_order = models.IntegerField(default=0, verbose_name='Thứ tự hiển thị')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Ngày tạo')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Ngày cập nhật')

    class Meta:
        verbose_name = 'Phân loại sản phẩm'
        verbose_name_plural = 'Phân loại sản phẩm'
        ordering = ['sort_order', 'created_at']

    def __str__(self):
        return f"{self.product.name} - {self.variant_name}"
    
    def save(self, *args, **kwargs):
        """Tự động bật has_variants cho product khi tạo variant"""
        super().save(*args, **kwargs)
        # Tự động bật has_variants nếu chưa bật
        if not self.product.has_variants:
            self.product.has_variants = True
            self.product.save(update_fields=['has_variants'])
    
    def delete(self, *args, **kwargs):
        """Tự động tắt has_variants nếu không còn variants"""
        product = self.product
        super().delete(*args, **kwargs)
        # Nếu không còn variants nào, tắt has_variants
        if not product.variants.exists():
            product.has_variants = False
            product.save(update_fields=['has_variants'])
    
    @property
    def display_image(self):
        """Lấy hình ảnh của variant hoặc hình ảnh mặc định của product"""
        if self.image:
            return self.image
        return self.product.get_primary_image
    
    @property
    def is_in_stock(self):
        """Kiểm tra còn hàng"""
        return self.stock > 0


# Cart Item Model
class CartItem(models.Model):
    cart_item_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='cart_items', verbose_name='Người dùng')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='cart_items', verbose_name='Sản phẩm')
    variant = models.ForeignKey('ProductVariant', on_delete=models.CASCADE, related_name='cart_items', null=True, blank=True, verbose_name='Phân loại')
    quantity = models.IntegerField(default=1, verbose_name='Số lượng')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Ngày thêm')

    class Meta:
        verbose_name = 'Mục giỏ hàng'
        verbose_name_plural = 'Các mục giỏ hàng'
        unique_together = ('user', 'product', 'variant')

    def __str__(self):
        variant_str = f" - {self.variant.variant_name}" if self.variant else ""
        return f"{self.quantity} x {self.product.name}{variant_str} by {self.user.phone_number}"
    
    @property
    def total_price(self):
        """Tính tổng giá dựa trên variant hoặc product"""
        price = self.variant.price if self.variant else self.product.price
        return price * self.quantity
    
    @property
    def unit_price(self):
        """Lấy đơn giá"""
        return self.variant.price if self.variant else self.product.price


# Order Model
class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Đang chờ xác nhận'),
        ('waiting_pickup', 'Đang chờ shipper đến lấy hàng'),
        ('shipping', 'Đang giao hàng'),
        ('delivered', 'Đã nhận hàng'),
        ('cancelled', 'Đã hủy'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('cod', 'Thanh toán khi nhận hàng (COD)'),
        ('bank_transfer', 'Chuyển khoản ngân hàng'),
        ('credit_card', 'Thẻ tín dụng'),
        ('vnpay', 'VnPay'),
        ('zalopay', 'ZaloPay'),
    ]

    order_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='orders', verbose_name='Người dùng')
    shipping_address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders', verbose_name='Địa chỉ giao hàng')
    
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending', verbose_name='Trạng thái đơn hàng')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Tổng tiền hàng')
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Số tiền giảm giá')
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Phí vận chuyển')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Tổng cộng')
    
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES, default='cod', verbose_name='Phương thức thanh toán')
    payment_status = models.CharField(
        max_length=50, 
        default='pending', 
        choices=[
            ('pending', 'Chưa thanh toán'),
            ('paid', 'Đã thanh toán'),
            ('failed', 'Thanh toán thất bại'),
            ('refunded', 'Đã hoàn tiền'),
        ], 
        verbose_name='Trạng thái thanh toán'
    )
    
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Ngày tạo')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Ngày cập nhật')
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian thanh toán')
    notes = models.TextField(blank=True, null=True, verbose_name='Ghi chú')
    
    class Meta:
        verbose_name = 'Đơn hàng'
        verbose_name_plural = 'Đơn hàng'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Đơn hàng #{self.order_id} - {self.user.phone_number} - {self.get_status_display()}"


# Order Item Model
class OrderItem(models.Model):
    order_item_id = models.AutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items', verbose_name='Đơn hàng')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='order_items', verbose_name='Sản phẩm')
    variant = models.ForeignKey('ProductVariant', on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items', verbose_name='Phân loại')
    quantity = models.IntegerField(verbose_name='Số lượng')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Đơn giá')
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Thành tiền')
    
    class Meta:
        verbose_name = 'Chi tiết đơn hàng'
        verbose_name_plural = 'Chi tiết đơn hàng'
    
    def __str__(self):
        variant_str = f" - {self.variant.variant_name}" if self.variant else ""
        return f"{self.quantity} x {self.product.name}{variant_str} trong đơn hàng #{self.order.order_id}"
    
    def save(self, *args, **kwargs):
        # Nếu chưa có unit_price, lấy từ variant hoặc product
        if not self.unit_price:
            if self.variant:
                self.unit_price = self.variant.price
            else:
                self.unit_price = self.product.price
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)


# Review Model
class Review(models.Model):
    review_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='reviews', verbose_name='Người dùng')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews', verbose_name='Sản phẩm')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='reviews', verbose_name='Đơn hàng', null=True, blank=True)
    order_item = models.ForeignKey('OrderItem', on_delete=models.CASCADE, related_name='reviews', verbose_name='Chi tiết đơn hàng', null=True, blank=True)
    
    rating = models.IntegerField(verbose_name='Đánh giá', choices=[
        (1, '1 sao'),
        (2, '2 sao'),
        (3, '3 sao'),
        (4, '4 sao'),
        (5, '5 sao'),
    ])
    content = models.TextField(verbose_name='Nội dung đánh giá')
    
    seller_reply = models.TextField(blank=True, null=True, verbose_name='Phản hồi của cửa hàng')
    seller_replied_at = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian phản hồi')
    
    is_verified_purchase = models.BooleanField(default=True, verbose_name='Xác minh mua hàng')
    is_approved = models.BooleanField(default=True, verbose_name='Đã duyệt')
    
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Ngày tạo')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Ngày cập nhật')
    
    class Meta:
        verbose_name = 'Đánh giá sản phẩm'
        verbose_name_plural = 'Đánh giá sản phẩm'
        unique_together = ('user', 'order_item')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Đánh giá {self.rating} sao cho {self.product.name} bởi {self.user.phone_number}"
    
    @property
    def has_seller_reply(self):
        """Check if review has seller reply"""
        return bool(self.seller_reply)


# Review Media Model
class ReviewMedia(models.Model):
    MEDIA_TYPE_CHOICES = [
        ('image', 'Hình ảnh'),
        ('video', 'Video'),
    ]
    
    media_id = models.AutoField(primary_key=True)
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='media_files', verbose_name='Đánh giá')
    file = models.FileField(upload_to='reviews/media/', verbose_name='File')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, verbose_name='Loại media')
    order = models.PositiveIntegerField(default=0, verbose_name='Thứ tự')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Ngày tạo')
    
    class Meta:
        verbose_name = 'Media đánh giá'
        verbose_name_plural = 'Media đánh giá'
        ordering = ['order', 'created_at']
    
    def __str__(self):
        return f"{self.get_media_type_display()} cho review #{self.review.review_id}"


# Product Comment Model
class ProductComment(models.Model):
    comment_id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='comments', verbose_name='Sản phẩm')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='product_comments', verbose_name='Người dùng')
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='comments', verbose_name='Chi tiết đơn hàng', null=True, blank=True)
    content = models.TextField(verbose_name='Nội dung bình luận')
    
    seller_reply = models.TextField(blank=True, null=True, verbose_name='Phản hồi của cửa hàng')
    seller_replied_at = models.DateTimeField(null=True, blank=True, verbose_name='Thời gian phản hồi')
    
    is_approved = models.BooleanField(default=True, verbose_name='Đã duyệt')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Ngày tạo')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Ngày cập nhật')
    
    class Meta:
        verbose_name = 'Bình luận sản phẩm'
        verbose_name_plural = 'Bình luận sản phẩm'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Bình luận của {self.user.full_name} cho {self.product.name}"
    
    @property
    def has_seller_reply(self):
        """Check if comment has seller reply"""
        return bool(self.seller_reply)


# Store Review Stats Model - Cache thống kê
class StoreReviewStats(models.Model):
    store = models.OneToOneField(Store, on_delete=models.CASCADE, related_name='review_stats', verbose_name='Cửa hàng')
    last_accessed_at = models.DateTimeField(null=True, blank=True, verbose_name='Lần truy cập cuối')
    total_reviews_30d = models.IntegerField(default=0, verbose_name='Tổng đánh giá 30 ngày')
    avg_rating_30d = models.DecimalField(max_digits=3, decimal_places=2, default=0.00, verbose_name='Đánh giá trung bình 30 ngày')
    good_reviews_count = models.IntegerField(default=0, verbose_name='Số đánh giá tốt (4-5 sao)')
    negative_reviews_count = models.IntegerField(default=0, verbose_name='Số đánh giá tiêu cực (1-2 sao)')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Ngày cập nhật')
    
    class Meta:
        verbose_name = 'Thống kê đánh giá cửa hàng'
        verbose_name_plural = 'Thống kê đánh giá cửa hàng'
    
    def __str__(self):
        return f"Thống kê đánh giá cho {self.store.store_name}"


