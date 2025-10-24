import random
import string
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class RedisOTPManager:
    """Manages OTP storage and validation using Redis"""
    
    @staticmethod
    def generate_otp() -> str:
        """Generate random 6-digit OTP code"""
        return ''.join(random.choices(string.digits, k=6))
    
    @staticmethod
    def store_otp(user_id: int, otp_code: str, ttl_minutes: int = 5):
        """Store OTP in Redis with TTL"""
        cache_key = f"otp:{user_id}"
        cache.set(cache_key, otp_code, timeout=ttl_minutes * 60)
    
    @staticmethod
    def get_otp(user_id: int) -> str | None:
        """Retrieve OTP from Redis"""
        cache_key = f"otp:{user_id}"
        return cache.get(cache_key)
    
    @staticmethod
    def verify_otp(user_id: int, otp_code: str) -> bool:
        """Validate OTP and delete if correct"""
        stored_otp = RedisOTPManager.get_otp(user_id)
        if stored_otp and stored_otp == otp_code:
            # Delete OTP after successful verification
            RedisOTPManager.delete_otp(user_id)
            return True
        return False
    
    @staticmethod
    def delete_otp(user_id: int):
        """Remove OTP from Redis"""
        cache_key = f"otp:{user_id}"
        cache.delete(cache_key)
    
    @staticmethod
    def check_resend_limit(user_id: int) -> tuple[bool, int]:
        """
        Check if user can resend OTP (1 minute cooldown)
        Returns: (can_resend, seconds_remaining)
        """
        cooldown_key = f"otp_cooldown:{user_id}"
        last_resend = cache.get(cooldown_key)
        
        if last_resend is None:
            return True, 0
        
        # Check if 1 minute has passed
        cooldown_seconds = getattr(settings, 'OTP_RESEND_COOLDOWN_MINUTES', 1) * 60
        time_since_last_resend = (timezone.now() - last_resend).total_seconds()
        
        if time_since_last_resend >= cooldown_seconds:
            return True, 0
        else:
            remaining_seconds = int(cooldown_seconds - time_since_last_resend)
            return False, remaining_seconds
    
    @staticmethod
    def increment_resend_count(user_id: int):
        """Track resend attempts in Redis with 1-minute TTL"""
        cooldown_key = f"otp_cooldown:{user_id}"
        cache.set(cooldown_key, timezone.now(), timeout=60)  # 1 minute TTL
    
    @staticmethod
    def get_remaining_time(user_id: int) -> int:
        """Get remaining cooldown time in seconds"""
        cooldown_key = f"otp_cooldown:{user_id}"
        last_resend = cache.get(cooldown_key)
        
        if last_resend is None:
            return 0
        
        cooldown_seconds = getattr(settings, 'OTP_RESEND_COOLDOWN_MINUTES', 1) * 60
        time_since_last_resend = (timezone.now() - last_resend).total_seconds()
        remaining = int(cooldown_seconds - time_since_last_resend)
        
        return max(0, remaining)
