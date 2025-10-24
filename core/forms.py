from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import RegexValidator
from .models import CustomUser, Product, Order, Review, Address, ProductImage


class CustomUserRegistrationForm(UserCreationForm):
    phone_number = forms.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Số điện thoại phải theo định dạng: '+999999999'. Tối đa 15 chữ số."
            )
        ],
        widget=forms.TextInput(attrs={'placeholder': 'Số điện thoại'})
    )
    full_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'Họ và tên'})
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'placeholder': 'Email (tùy chọn)'})
    )

    class Meta:
        model = CustomUser
        fields = ('phone_number', 'full_name', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'placeholder': 'Mật khẩu'})
        self.fields['password2'].widget.attrs.update({'placeholder': 'Xác nhận mật khẩu'})


class LoginForm(forms.Form):
    phone_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'placeholder': 'Số điện thoại'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Mật khẩu'})
    )


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['full_name', 'phone_number', 'email', 'avatar']
        widgets = {
            'full_name': forms.TextInput(attrs={'placeholder': 'Họ và tên'}),
            'phone_number': forms.TextInput(attrs={'placeholder': 'Số điện thoại'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email'}),
            'avatar': forms.FileInput(attrs={'accept': 'image/*'}),
        }


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'base_unit', 'category', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Tên sản phẩm', 'class': 'form-control form-control-lg rounded-3'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Mô tả sản phẩm', 'class': 'form-control rounded-3'}),
            'price': forms.NumberInput(attrs={'placeholder': 'Giá sản phẩm', 'step': '0.01', 'class': 'form-control form-control-lg rounded-3'}),
            'base_unit': forms.TextInput(attrs={'placeholder': 'Đơn vị (kg, gói, chiếc...)', 'class': 'form-control form-control-lg rounded-3'}),
            'category': forms.Select(attrs={'class': 'form-select form-select-lg rounded-3'}),
            'image': forms.FileInput(attrs={'accept': 'image/*', 'class': 'form-control form-control-lg rounded-3'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make image field optional
        self.fields['image'].required = False
        self.fields['category'].required = False
        self.fields['base_unit'].required = False


class ProductImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ['image', 'alt_text', 'is_primary', 'order']
        widgets = {
            'image': forms.FileInput(attrs={'accept': 'image/*', 'class': 'form-control form-control-lg rounded-3'}),
            'alt_text': forms.TextInput(attrs={'placeholder': 'Mô tả hình ảnh', 'class': 'form-control rounded-3'}),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={'placeholder': 'Thứ tự hiển thị', 'class': 'form-control rounded-3'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['alt_text'].required = False
        self.fields['order'].required = False


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
        fields = ['rating', 'title', 'content']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Tiêu đề đánh giá'}),
            'content': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Nội dung đánh giá'}),
        }




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
        from .models import Category
        self.fields['category'].queryset = Category.objects.all()
