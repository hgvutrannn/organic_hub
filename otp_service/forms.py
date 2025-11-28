from django import forms


class EmailOTPVerificationForm(forms.Form):
    """Form for OTP verification"""
    
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter 6-digit OTP code',
            'class': 'form-control form-control-lg text-center',
            'pattern': '[0-9]{6}',
            'inputmode': 'numeric',
            'autocomplete': 'off',
            'style': 'font-size: 1.5rem; letter-spacing: 0.5rem;'
        }),
        label='OTP Verification Code',
        help_text='Enter the 6-digit code sent to your email'
    )
    
    def clean_otp_code(self):
        """Validate OTP code format"""
        otp_code = self.cleaned_data.get('otp_code')
        
        if not otp_code:
            raise forms.ValidationError('Please enter OTP code.')
        
        if not otp_code.isdigit():
            raise forms.ValidationError('OTP code must contain only numbers.')
        
        if len(otp_code) != 6:
            raise forms.ValidationError('OTP code must be exactly 6 digits.')
        
        return otp_code
