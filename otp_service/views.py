from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from django.conf import settings
from .forms import EmailOTPVerificationForm
from .service import OTPService

User = get_user_model()


def verify_otp(request, user_id):
    """OTP verification view"""
    user = get_object_or_404(User, user_id=user_id)
    
    # Check if user is already verified
    if user.email_verified:
        messages.info(request, 'Email của bạn đã được xác thực.')
        return redirect('home')
    
    if request.method == 'POST':
        form = EmailOTPVerificationForm(request.POST)
        if form.is_valid():
            otp_code = form.cleaned_data['otp_code']
            
            # Verify OTP using service
            result = OTPService.verify_otp(user_id, otp_code)
            
            if result['success']:
                # Mark user as verified
                user.email_verified = True
                user.save()
                
                # Auto-login user
                login(request, user)
                
                messages.success(request, 'Xác thực email thành công! Chào mừng bạn đến với Organic Hub.')
                return redirect('home')
            else:
                messages.error(request, result['message'])
    else:
        form = EmailOTPVerificationForm()
    
    # Get remaining cooldown time
    remaining_seconds = OTPService.get_remaining_cooldown(user_id)
    
    context = {
        'form': form,
        'user': user,
        'remaining_seconds': remaining_seconds,
        'expiry_minutes': getattr(settings, 'OTP_EXPIRY_MINUTES', 5),
    }
    
    return render(request, 'otp_service/verify_otp.html', context)


@require_POST
def resend_otp(request, user_id):
    """Resend OTP view (AJAX)"""
    try:
        result = OTPService.resend_otp(user_id, purpose='registration')
        
        return JsonResponse({
            'success': result['success'],
            'message': result['message'],
            'remaining_seconds': result.get('remaining_seconds', 0)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'Có lỗi xảy ra. Vui lòng thử lại.',
            'remaining_seconds': 0
        })