from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import random
import string


class EmailOTP(models.Model):
    """Model to store OTP codes for email verification"""
    
    PURPOSE_CHOICES = [
        ('registration', 'Đăng ký tài khoản'),
        ('password_reset', 'Đặt lại mật khẩu'),
        ('email_change', 'Thay đổi email'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='email_otps',
        verbose_name='Người dùng'
    )
    otp_code = models.CharField(
        max_length=6,
        verbose_name='Mã OTP'
    )
    purpose = models.CharField(
        max_length=20,
        choices=PURPOSE_CHOICES,
        default='registration',
        verbose_name='Mục đích'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Thời gian tạo'
    )
    expires_at = models.DateTimeField(
        verbose_name='Thời gian hết hạn'
    )
    is_verified = models.BooleanField(
        default=False,
        verbose_name='Đã xác thực'
    )
    is_used = models.BooleanField(
        default=False,
        verbose_name='Đã sử dụng'
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['expires_at']),
        ]
        verbose_name = 'Mã OTP Email'
        verbose_name_plural = 'Mã OTP Email'
    
    def __str__(self):
        return f"OTP for {self.user.full_name} - {self.purpose}"
    
    def is_valid(self):
        """Check if OTP is valid (not expired and not used)"""
        return (
            not self.is_used and 
            not self.is_verified and 
            timezone.now() < self.expires_at
        )
    
    def mark_as_used(self):
        """Mark OTP as used"""
        self.is_used = True
        self.is_verified = True
        self.save()
    
    @classmethod
    def create_otp(cls, user, purpose='registration'):
        """Create a new OTP for user"""
        # Generate 6-digit OTP
        otp_code = ''.join(random.choices(string.digits, k=6))
        
        # Set expiry time (5 minutes from now)
        expires_at = timezone.now() + timedelta(minutes=5)
        
        # Create OTP record
        otp = cls.objects.create(
            user=user,
            otp_code=otp_code,
            purpose=purpose,
            expires_at=expires_at
        )
        
        return otp
    
    @classmethod
    def get_valid_otp(cls, user, purpose='registration'):
        """Get the most recent valid OTP for user"""
        return cls.objects.filter(
            user=user,
            purpose=purpose,
            is_used=False,
            is_verified=False,
            expires_at__gt=timezone.now()
        ).first()
    
    @classmethod
    def invalidate_user_otps(cls, user, purpose='registration'):
        """Invalidate all existing OTPs for user"""
        cls.objects.filter(
            user=user,
            purpose=purpose,
            is_used=False
        ).update(is_used=True)