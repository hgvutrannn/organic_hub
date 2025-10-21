from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from django.core.validators import RegexValidator


# Custom User Manager
class CustomUserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, email=None, full_name=None, **extra_fields):
        if not phone_number:
            raise ValueError('Số điện thoại là bắt buộc')
        
        user = self.model(
            phone_number=phone_number,
            email=self.normalize_email(email) if email else None,
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
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['full_name']

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

    class Meta:
        verbose_name = 'Cửa hàng'
        verbose_name_plural = 'Cửa hàng'

    def __str__(self):
        return self.store_name


# Product Model
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
    view_count = models.PositiveIntegerField(default=0, verbose_name='Số lượt xem')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Ngày tạo')

    class Meta:
        verbose_name = 'Sản phẩm'
        verbose_name_plural = 'Sản phẩm'

    def __str__(self):
        return self.name


# Cart Item Model
class CartItem(models.Model):
    cart_item_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='cart_items', verbose_name='Người dùng')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='cart_items', verbose_name='Sản phẩm')
    quantity = models.IntegerField(default=1, verbose_name='Số lượng')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Ngày thêm')

    class Meta:
        verbose_name = 'Mục giỏ hàng'
        verbose_name_plural = 'Các mục giỏ hàng'
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.quantity} x {self.product.name} by {self.user.phone_number}"
    
    @property
    def total_price(self):
        return self.product.price * self.quantity


# Order Model
class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Đang chờ xử lý'),
        ('confirmed', 'Đã xác nhận'),
        ('processing', 'Đang xử lý'),
        ('shipped', 'Đã giao hàng'),
        ('delivered', 'Đã giao thành công'),
        ('cancelled', 'Đã hủy'),
        ('returned', 'Đã trả hàng'),
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
    quantity = models.IntegerField(verbose_name='Số lượng')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Đơn giá')
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Thành tiền')
    
    class Meta:
        verbose_name = 'Chi tiết đơn hàng'
        verbose_name_plural = 'Chi tiết đơn hàng'
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name} trong đơn hàng #{self.order.order_id}"
    
    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)


# Review Model
class Review(models.Model):
    review_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='reviews', verbose_name='Người dùng')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews', verbose_name='Sản phẩm')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='reviews', verbose_name='Đơn hàng', null=True, blank=True)
    
    rating = models.IntegerField(verbose_name='Đánh giá', choices=[
        (1, '1 sao'),
        (2, '2 sao'),
        (3, '3 sao'),
        (4, '4 sao'),
        (5, '5 sao'),
    ])
    title = models.CharField(max_length=255, verbose_name='Tiêu đề đánh giá')
    content = models.TextField(verbose_name='Nội dung đánh giá')
    
    is_verified_purchase = models.BooleanField(default=True, verbose_name='Xác minh mua hàng')
    is_approved = models.BooleanField(default=True, verbose_name='Đã duyệt')
    
    created_at = models.DateTimeField(default=timezone.now, verbose_name='Ngày tạo')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Ngày cập nhật')
    
    class Meta:
        verbose_name = 'Đánh giá sản phẩm'
        verbose_name_plural = 'Đánh giá sản phẩm'
        unique_together = ('user', 'product')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Đánh giá {self.rating} sao cho {self.product.name} bởi {self.user.phone_number}"


