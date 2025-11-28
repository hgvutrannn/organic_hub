from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import RegexValidator
from .models import CustomUser, Product, Order, Review, Address, ProductImage, StoreCertification, OrderItem, ProductVariant, Category, CertificationOrganization


class CustomUserRegistrationForm(UserCreationForm):
    full_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'Họ và tên'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'Email'})
    )

    class Meta:
        model = CustomUser
        fields = ('email', 'full_name', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'placeholder': 'Mật khẩu'})
        self.fields['password2'].widget.attrs.update({'placeholder': 'Xác nhận mật khẩu'})


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'Email'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Mật khẩu'})
    )


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['full_name', 'email', 'avatar']
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'Họ và tên'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email'}),
            'avatar': forms.FileInput(attrs={'accept': 'image/*'}),
        }


class ProductForm(forms.ModelForm):
    has_variants = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'has_variants'}),
        label='Có phân loại sản phẩm',
        help_text='Bật tính năng này nếu sản phẩm có nhiều phân loại với giá và hình ảnh khác nhau'
    )
    
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'base_unit', 'stock', 'SKU', 'category', 'has_variants']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Tên sản phẩm', 'class': 'form-control form-control-lg rounded-3'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Mô tả sản phẩm', 'class': 'form-control rounded-3'}),
            'price': forms.NumberInput(attrs={'placeholder': 'Giá sản phẩm', 'step': '0.01', 'class': 'form-control form-control-lg rounded-3'}),
            'base_unit': forms.TextInput(attrs={'placeholder': 'Đơn vị (kg, gói, chiếc...)', 'class': 'form-control form-control-lg rounded-3'}),
            'stock': forms.NumberInput(attrs={'placeholder': 'Số lượng tồn kho', 'min': '0', 'class': 'form-control form-control-lg rounded-3'}),
            'SKU': forms.TextInput(attrs={'placeholder': 'Mã SKU (tự động nếu để trống)', 'class': 'form-control form-control-lg rounded-3'}),
            'category': forms.Select(attrs={'class': 'form-select form-select-lg rounded-3'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make fields optional
        self.fields['category'].required = False
        self.fields['base_unit'].required = False
        self.fields['SKU'].required = False
        
        # Disable has_variants checkbox if product has variants
        if self.instance and self.instance.pk:
            if self.instance.variants.exists():
                self.fields['has_variants'].widget.attrs['disabled'] = True
                self.fields['has_variants'].help_text = 'Không thể tắt chế độ phân loại khi còn phân loại. Vui lòng xóa hết phân loại trước.'
                # If product has variants, price is optional
                self.fields['price'].required = False
        else:
            # For new products, check POST data if available
            # args[0] could be QueryDict (from request.POST) or regular dict
            if args and len(args) > 0:
                data = args[0]
                # Handle both QueryDict and regular dict
                if hasattr(data, 'get'):
                    has_variants = data.get('has_variants', False)
                    # QueryDict returns list, so check if it's truthy
                    if isinstance(has_variants, list):
                        has_variants = has_variants[0] if has_variants else False
                    if has_variants and str(has_variants).lower() in ('true', '1', 'on'):
                        self.fields['price'].required = False
    
    def clean(self):
        """Custom validation for price when has_variants is True"""
        cleaned_data = super().clean()
        has_variants = cleaned_data.get('has_variants', False)
        price = cleaned_data.get('price')
        
        # If has_variants is True, price can be empty (will be set to 0 or min variant price)
        if has_variants and (price is None or price == ''):
            # Set a default price of 0 when has variants
            cleaned_data['price'] = 0
        
        # If no variants, price is required
        if not has_variants and (price is None or price == ''):
            raise forms.ValidationError({
                'price': 'Price is required when product does not have variants.'
            })
        
        return cleaned_data
    
    def clean_has_variants(self):
        """Prevent disabling has_variants if variants exist"""
        has_variants = self.cleaned_data.get('has_variants')
        if self.instance and self.instance.pk:
            if not has_variants and self.instance.variants.exists():
                raise forms.ValidationError('Không thể tắt chế độ phân loại khi còn phân loại. Vui lòng xóa hết phân loại trước.')
        return has_variants


class ProductImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ['image', 'alt_text', 'order']
        widgets = {
            'image': forms.FileInput(attrs={'accept': 'image/*', 'class': 'form-control form-control-lg rounded-3'}),
            'alt_text': forms.TextInput(attrs={'placeholder': 'Mô tả hình ảnh', 'class': 'form-control rounded-3'}),
            'order': forms.NumberInput(attrs={
                'placeholder': 'Thứ tự hiển thị (0 = ảnh chính)', 
                'class': 'form-control rounded-3',
                'min': '0'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['alt_text'].required = False
        self.fields['order'].required = False
        self.fields['order'].help_text = 'Đặt order=0 để làm ảnh chính'


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ['contact_person', 'contact_phone', 'street', 'ward', 'province', 'is_default']
        widgets = {
            'contact_person': forms.TextInput(attrs={'placeholder': 'Tên người nhận'}),
            'contact_phone': forms.TextInput(attrs={'placeholder': 'Số điện thoại người nhận'}),
            'street': forms.TextInput(attrs={'placeholder': 'Số nhà, tên đường'}),
            'ward': forms.TextInput(attrs={'placeholder': 'Phường/Xã'}),
            'province': forms.TextInput(attrs={'placeholder': 'Tỉnh/Thành phố'}),
        }


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'content']
        widgets = {
            'rating': forms.Select(attrs={'class': 'form-select'}),
            'content': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Nội dung đánh giá', 'class': 'form-control'}),
        }
    
    # Note: Multiple file uploads (images/videos) will be handled in views using request.FILES.getlist()




class SearchForm(forms.Form):
    query = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Tìm kiếm sản phẩm...'})
    )
    category = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Tất cả danh mục"
    )
    certificate = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="Tất cả chứng nhận"
    )
    min_price = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Giá tối thiểu', 'step': '0.01'})
    )
    max_price = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Giá tối đa', 'step': '0.01'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Category, CertificationOrganization
        self.fields['category'].queryset = Category.objects.all()
        self.fields['certificate'].queryset = CertificationOrganization.objects.filter(is_active=True)


class StoreCertificationForm(forms.ModelForm):
    class Meta:
        model = StoreCertification
        fields = ['certification_organization', 'document']
        widgets = {
            'certification_organization': forms.Select(attrs={'class': 'form-select form-select-lg rounded-3'}),
            'document': forms.FileInput(attrs={
                'accept': 'image/*,.pdf',
                'class': 'form-control form-control-lg rounded-3',
                'multiple': False
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['certification_organization'].required = False
        self.fields['certification_organization'].queryset = CertificationOrganization.objects.filter(is_active=True).order_by('name')
        self.fields['certification_organization'].empty_label = 'Chọn tổ chức cấp phép (tùy chọn)'


class AdminStoreReviewForm(forms.Form):
    """Form for admin to review and approve/reject stores"""
    action = forms.ChoiceField(
        choices=[
            ('approve', 'Phê duyệt'),
            ('reject', 'Từ chối'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    admin_notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Ghi chú của admin (bắt buộc khi từ chối)',
            'class': 'form-control rounded-3'
        }),
        required=False,
        help_text="Ghi chú này sẽ được hiển thị cho chủ cửa hàng."
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        admin_notes = cleaned_data.get('admin_notes')
        
        if action == 'reject' and not admin_notes:
            raise forms.ValidationError('Vui lòng nhập lý do từ chối.')
        
        return cleaned_data


# Password Change & Reset Forms
class PasswordChangeForm(forms.Form):
    """Form for changing password from profile page"""
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Nhập mật khẩu hiện tại',
            'class': 'form-control form-control-lg'
        }),
        label='Mật khẩu hiện tại'
    )
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Nhập mật khẩu mới',
            'class': 'form-control form-control-lg'
        }),
        label='Mật khẩu mới'
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Xác nhận mật khẩu mới',
            'class': 'form-control form-control-lg'
        }),
        label='Xác nhận mật khẩu mới'
    )
    
    def __init__(self, user=None, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        if old_password and not self.user.check_password(old_password):
            raise forms.ValidationError('Mật khẩu hiện tại không đúng.')
        return old_password
    
    def clean(self):
        cleaned_data = super().clean()
        new_password1 = cleaned_data.get('new_password1')
        new_password2 = cleaned_data.get('new_password2')
        
        if new_password1 and new_password2:
            if new_password1 != new_password2:
                raise forms.ValidationError('Mật khẩu mới không khớp.')
            if len(new_password1) < 8:
                raise forms.ValidationError('Mật khẩu mới phải có ít nhất 8 ký tự.')
        
        return cleaned_data


class ForgotPasswordForm(forms.Form):
    """Form for requesting password reset"""
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'Nhập email của bạn',
            'class': 'form-control form-control-lg'
        }),
        label='Email'
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            from .models import CustomUser
            try:
                user = CustomUser.objects.get(email=email)
                if not user.email_verified:
                    raise forms.ValidationError('Email chưa được xác thực. Vui lòng xác thực email trước.')
            except CustomUser.DoesNotExist:
                raise forms.ValidationError('Email không tồn tại trong hệ thống.')
        return email


class PasswordResetConfirmForm(forms.Form):
    """Form for setting new password after OTP verification"""
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Nhập mật khẩu mới',
            'class': 'form-control form-control-lg'
        }),
        label='Mật khẩu mới'
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Xác nhận mật khẩu mới',
            'class': 'form-control form-control-lg'
        }),
        label='Xác nhận mật khẩu mới'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        new_password1 = cleaned_data.get('new_password1')
        new_password2 = cleaned_data.get('new_password2')
        
        if new_password1 and new_password2:
            if new_password1 != new_password2:
                raise forms.ValidationError('Mật khẩu mới không khớp.')
            if len(new_password1) < 8:
                raise forms.ValidationError('Mật khẩu mới phải có ít nhất 8 ký tự.')
        
        return cleaned_data


class OTPVerificationForm(forms.Form):
    """Reusable OTP verification form"""
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'placeholder': 'Nhập mã OTP 6 số',
            'class': 'form-control form-control-lg text-center',
            'maxlength': '6',
            'pattern': '[0-9]{6}'
        }),
        label='Mã OTP',
        help_text='Nhập mã 6 số đã được gửi đến email của bạn'
    )
    
    def clean_otp_code(self):
        otp_code = self.cleaned_data.get('otp_code')
        if otp_code and not otp_code.isdigit():
            raise forms.ValidationError('Mã OTP chỉ chứa số.')
        return otp_code


# Review Forms
class ReviewReplyForm(forms.Form):
    seller_reply = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Viết phản hồi của cửa hàng...',
            'class': 'form-control'
        }),
        label='Phản hồi'
    )


# Store Review Filter Form
class StoreReviewFilterForm(forms.Form):
    STATUS_CHOICES = [
        ('all', 'Tất cả'),
        ('needs_reply', 'Cần phản hồi'),
        ('replied', 'Đã trả lời'),
    ]
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        initial='all',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    rating = forms.MultipleChoiceField(
        choices=[
            (1, '1 sao'),
            (2, '2 sao'),
            (3, '3 sao'),
            (4, '4 sao'),
            (5, '5 sao'),
        ],
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    product_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Tên sản phẩm',
            'class': 'form-control'
        })
    )
    
    order_id = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'placeholder': 'Mã đơn hàng',
            'class': 'form-control'
        })
    )
    
    buyer_username = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Tên đăng nhập người mua',
            'class': 'form-control'
        })
    )


# Certification Organization Forms
class CertificationOrganizationForm(forms.ModelForm):
    class Meta:
        model = CertificationOrganization
        fields = ['name', 'abbreviation', 'description', 'website', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Tên tổ chức',
                'class': 'form-control form-control-lg rounded-3'
            }),
            'abbreviation': forms.TextInput(attrs={
                'placeholder': 'Viết tắt',
                'class': 'form-control form-control-lg rounded-3'
            }),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Mô tả về tổ chức',
                'class': 'form-control rounded-3'
            }),
            'website': forms.URLInput(attrs={
                'placeholder': 'https://example.com',
                'class': 'form-control form-control-lg rounded-3'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False
        self.fields['website'].required = False


# Category Forms
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'slug']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Tên danh mục',
                'class': 'form-control form-control-lg rounded-3'
            }),
            'slug': forms.TextInput(attrs={
                'placeholder': 'Slug (tự động tạo từ tên)',
                'class': 'form-control form-control-lg rounded-3'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['slug'].help_text = 'Slug sẽ được tự động tạo từ tên danh mục nếu để trống'
    
    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        if not slug:
            # Auto-generate slug from name
            from django.utils.text import slugify
            name = self.cleaned_data.get('name', '')
            slug = slugify(name)
        
        # Check uniqueness
        existing = Category.objects.filter(slug=slug)
        if self.instance and self.instance.pk:
            existing = existing.exclude(category_id=self.instance.category_id)
        if existing.exists():
            raise forms.ValidationError('Slug này đã tồn tại. Vui lòng chọn slug khác.')
        
        return slug
