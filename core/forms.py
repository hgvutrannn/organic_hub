from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import RegexValidator
from .models import CustomUser, Product, Order, Review, Address, ProductImage, StoreCertification, OrderItem, ProductVariant, Category, CertificationOrganization


class CustomUserRegistrationForm(UserCreationForm):
    full_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'Full Name'})
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
        self.fields['password1'].widget.attrs.update({'placeholder': 'Password'})
        self.fields['password2'].widget.attrs.update({'placeholder': 'Confirm Password'})


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'Email'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Password'})
    )


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['full_name', 'email', 'avatar']
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'Full Name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email'}),
            'avatar': forms.FileInput(attrs={'accept': 'image/*'}),
        }


class ProductForm(forms.ModelForm):
    has_variants = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'has_variants'}),
        label='Product has variants',
        help_text='Enable this if the product has multiple variants with different prices and images'
    )
    
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'base_unit', 'stock', 'SKU', 'category', 'has_variants']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Product Name', 'class': 'form-control form-control-lg rounded-3'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Product Description', 'class': 'form-control rounded-3'}),
            'price': forms.NumberInput(attrs={'placeholder': 'Product Price', 'step': '0.01', 'class': 'form-control form-control-lg rounded-3'}),
            'base_unit': forms.TextInput(attrs={'placeholder': 'Unit (kg, box, piece...)', 'class': 'form-control form-control-lg rounded-3'}),
            'stock': forms.NumberInput(attrs={'placeholder': 'Stock Quantity', 'min': '0', 'class': 'form-control form-control-lg rounded-3'}),
            'SKU': forms.TextInput(attrs={'placeholder': 'SKU Code (auto-generated if empty)', 'class': 'form-control form-control-lg rounded-3'}),
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
                self.fields['has_variants'].help_text = 'Cannot disable variant mode when variants exist. Please delete all variants first.'
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
                raise forms.ValidationError('Cannot disable variant mode when variants exist. Please delete all variants first.')
        return has_variants


class ProductImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ['image', 'alt_text', 'order']
        widgets = {
            'image': forms.FileInput(attrs={'accept': 'image/*', 'class': 'form-control form-control-lg rounded-3'}),
            'alt_text': forms.TextInput(attrs={'placeholder': 'Image Description', 'class': 'form-control rounded-3'}),
            'order': forms.NumberInput(attrs={
                'placeholder': 'Display Order (0 = primary image)', 
                'class': 'form-control rounded-3',
                'min': '0'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['alt_text'].required = False
        self.fields['order'].required = False
        self.fields['order'].help_text = 'Set order=0 to make it the primary image'


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ['contact_person', 'contact_phone', 'street', 'ward', 'province', 'is_default']
        widgets = {
            'contact_person': forms.TextInput(attrs={'placeholder': 'Recipient Name'}),
            'contact_phone': forms.TextInput(attrs={'placeholder': 'Recipient Phone'}),
            'street': forms.TextInput(attrs={'placeholder': 'Street Address'}),
            'ward': forms.TextInput(attrs={'placeholder': 'Ward/Commune'}),
            'province': forms.TextInput(attrs={'placeholder': 'Province/City'}),
        }


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'content']
        widgets = {
            'rating': forms.Select(attrs={'class': 'form-select'}),
            'content': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Review Content', 'class': 'form-control'}),
        }
    
    # Note: Multiple file uploads (images/videos) will be handled in views using request.FILES.getlist()




class SearchForm(forms.Form):
    query = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Search products...'})
    )
    category = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="All Categories"
    )
    certificate = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label="All Certifications"
    )
    min_price = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Minimum Price', 'step': '0.01'})
    )
    max_price = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Maximum Price', 'step': '0.01'})
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
        self.fields['certification_organization'].empty_label = 'Select Certification Organization (optional)'


class AdminStoreReviewForm(forms.Form):
    """Form for admin to review and approve/reject stores"""
    action = forms.ChoiceField(
        choices=[
            ('approve', 'Approve'),
            ('reject', 'Reject'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    admin_notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Admin Notes (required when rejecting)',
            'class': 'form-control rounded-3'
        }),
        required=False,
        help_text="This note will be displayed to the store owner."
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        admin_notes = cleaned_data.get('admin_notes')
        
        if action == 'reject' and not admin_notes:
            raise forms.ValidationError('Please enter the reason for rejection.')
        
        return cleaned_data


# Password Change & Reset Forms
class PasswordChangeForm(forms.Form):
    """Form for changing password from profile page"""
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter current password',
            'class': 'form-control form-control-lg'
        }),
        label='Current Password'
    )
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter new password',
            'class': 'form-control form-control-lg'
        }),
        label='New Password'
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirm new password',
            'class': 'form-control form-control-lg'
        }),
        label='Confirm New Password'
    )
    
    def __init__(self, user=None, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        if old_password and not self.user.check_password(old_password):
            raise forms.ValidationError('Current password is incorrect.')
        return old_password
    
    def clean(self):
        cleaned_data = super().clean()
        new_password1 = cleaned_data.get('new_password1')
        new_password2 = cleaned_data.get('new_password2')
        
        if new_password1 and new_password2:
            if new_password1 != new_password2:
                raise forms.ValidationError('New passwords do not match.')
            if len(new_password1) < 8:
                raise forms.ValidationError('New password must be at least 8 characters long.')
        
        return cleaned_data


class ForgotPasswordForm(forms.Form):
    """Form for requesting password reset"""
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'placeholder': 'Enter your email',
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
                    raise forms.ValidationError('Email is not verified. Please verify your email first.')
            except CustomUser.DoesNotExist:
                raise forms.ValidationError('Email does not exist in the system.')
        return email


class PasswordResetConfirmForm(forms.Form):
    """Form for setting new password after OTP verification"""
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter new password',
            'class': 'form-control form-control-lg'
        }),
        label='New Password'
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirm new password',
            'class': 'form-control form-control-lg'
        }),
        label='Confirm New Password'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        new_password1 = cleaned_data.get('new_password1')
        new_password2 = cleaned_data.get('new_password2')
        
        if new_password1 and new_password2:
            if new_password1 != new_password2:
                raise forms.ValidationError('New passwords do not match.')
            if len(new_password1) < 8:
                raise forms.ValidationError('New password must be at least 8 characters long.')
        
        return cleaned_data


class OTPVerificationForm(forms.Form):
    """Reusable OTP verification form"""
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter 6-digit OTP code',
            'class': 'form-control form-control-lg text-center',
            'maxlength': '6',
            'pattern': '[0-9]{6}'
        }),
        label='OTP Code',
        help_text='Enter the 6-digit code sent to your email'
    )
    
    def clean_otp_code(self):
        otp_code = self.cleaned_data.get('otp_code')
        if otp_code and not otp_code.isdigit():
            raise forms.ValidationError('OTP code must contain only numbers.')
        return otp_code


# Review Forms
class ReviewReplyForm(forms.Form):
    seller_reply = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Write store reply...',
            'class': 'form-control'
        }),
        label='Reply'
    )


# Store Review Filter Form
class StoreReviewFilterForm(forms.Form):
    STATUS_CHOICES = [
        ('all', 'All'),
        ('needs_reply', 'Needs Reply'),
        ('replied', 'Replied'),
    ]
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        initial='all',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    rating = forms.MultipleChoiceField(
        choices=[
            (1, '1 star'),
            (2, '2 stars'),
            (3, '3 stars'),
            (4, '4 stars'),
            (5, '5 stars'),
        ],
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    product_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Product Name',
            'class': 'form-control'
        })
    )
    
    order_id = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'placeholder': 'Order ID',
            'class': 'form-control'
        })
    )
    
    buyer_username = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Buyer Username',
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
                'placeholder': 'Organization Name',
                'class': 'form-control form-control-lg rounded-3'
            }),
            'abbreviation': forms.TextInput(attrs={
                'placeholder': 'Abbreviation',
                'class': 'form-control form-control-lg rounded-3'
            }),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Organization Description',
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
                'placeholder': 'Category Name',
                'class': 'form-control form-control-lg rounded-3'
            }),
            'slug': forms.TextInput(attrs={
                'placeholder': 'Slug (auto-generated from name)',
                'class': 'form-control form-control-lg rounded-3'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['slug'].help_text = 'Slug will be automatically generated from category name if left empty'
    
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
            raise forms.ValidationError('This slug already exists. Please choose a different slug.')
        
        return slug
