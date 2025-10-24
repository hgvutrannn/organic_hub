from django import forms


class EmailOTPVerificationForm(forms.Form):
    """Form for OTP verification"""
    
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'placeholder': 'Nhập mã OTP 6 số',
            'class': 'form-control form-control-lg text-center',
            'pattern': '[0-9]{6}',
            'inputmode': 'numeric',
            'autocomplete': 'off',
            'style': 'font-size: 1.5rem; letter-spacing: 0.5rem;'
        }),
        label='Mã xác thực OTP',
        help_text='Nhập mã 6 số đã được gửi đến email của bạn'
    )
    
    def clean_otp_code(self):
        """Validate OTP code format"""
        otp_code = self.cleaned_data.get('otp_code')
        
        if not otp_code:
            raise forms.ValidationError('Vui lòng nhập mã OTP.')
        
        if not otp_code.isdigit():
            raise forms.ValidationError('Mã OTP chỉ được chứa số.')
        
        if len(otp_code) != 6:
            raise forms.ValidationError('Mã OTP phải có đúng 6 số.')
        
        return otp_code
