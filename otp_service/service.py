from django.contrib.auth import get_user_model
from django.conf import settings
from .models import EmailOTP
from .otp_manager import RedisOTPManager
from .tasks import send_otp_email_task
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class OTPService:
    """Main service class for OTP operations"""
    
    @staticmethod
    def generate_and_send_otp(user, purpose='registration') -> dict:
        """
        Generate OTP, store in Redis + DB, send email via Celery
        Returns: {'success': bool, 'message': str}
        """
        try:
            # Generate OTP code
            otp_code = RedisOTPManager.generate_otp()
            
            # Print OTP generation info
            print(f"🔐 GENERATING OTP:")
            print(f"   👤 User: {user.full_name} (ID: {user.user_id})")
            print(f"   📧 Email: {user.email}")
            print(f"   🔢 OTP Code: {otp_code}")
            print(f"   🎯 Purpose: {purpose}")
            print(f"   ⏰ Expires in: {getattr(settings, 'OTP_EXPIRY_MINUTES', 5)} minutes")
            print("=" * 50)
            
            # Store in Redis with TTL
            expiry_minutes = getattr(settings, 'OTP_EXPIRY_MINUTES', 5)
            RedisOTPManager.store_otp(user.user_id, otp_code, expiry_minutes)
            
            # Create database record
            EmailOTP.invalidate_user_otps(user, purpose)  # Invalidate old OTPs
            otp_record = EmailOTP.create_otp(user, purpose)
            
            # Send email via Celery (async)
            print(f"📤 QUEUEING EMAIL TASK...")
            send_otp_email_task.delay(user.user_id, otp_code, purpose)
            
            logger.info(f"OTP generated and sent for user {user.user_id}")
            return {
                'success': True,
                'message': 'Mã OTP đã được gửi đến email của bạn.'
            }
            
        except Exception as e:
            logger.error(f"Failed to generate and send OTP for user {user.user_id}: {str(e)}")
            return {
                'success': False,
                'message': 'Có lỗi khi gửi mã OTP. Vui lòng thử lại.'
            }
    
    @staticmethod
    def verify_otp(user_id: int, otp_code: str) -> dict:
        """
        Verify OTP from Redis, mark as used in DB
        Returns: {'success': bool, 'message': str}
        """
        try:
            # Verify OTP from Redis
            if RedisOTPManager.verify_otp(user_id, otp_code):
                # Mark as used in database
                user = User.objects.get(user_id=user_id)
                otp_record = EmailOTP.get_valid_otp(user, 'registration')
                if otp_record:
                    otp_record.mark_as_used()
                
                logger.info(f"OTP verified successfully for user {user_id}")
                return {
                    'success': True,
                    'message': 'Mã OTP hợp lệ.'
                }
            else:
                return {
                    'success': False,
                    'message': 'Mã OTP không đúng hoặc đã hết hạn.'
                }
                
        except User.DoesNotExist:
            return {
                'success': False,
                'message': 'Người dùng không tồn tại.'
            }
        except Exception as e:
            logger.error(f"Failed to verify OTP for user {user_id}: {str(e)}")
            return {
                'success': False,
                'message': 'Có lỗi khi xác thực mã OTP. Vui lòng thử lại.'
            }
    
    @staticmethod
    def resend_otp(user_id: int, purpose='registration') -> dict:
        """
        Check rate limit, generate new OTP, send email
        Returns: {'success': bool, 'message': str, 'remaining_seconds': int}
        """
        try:
            # Check resend cooldown
            can_resend, remaining_seconds = RedisOTPManager.check_resend_limit(user_id)
            
            if not can_resend:
                return {
                    'success': False,
                    'message': f'Vui lòng đợi {remaining_seconds} giây trước khi gửi lại mã OTP.',
                    'remaining_seconds': remaining_seconds
                }
            
            # Get user
            user = User.objects.get(user_id=user_id)
            
            # Generate new OTP
            result = OTPService.generate_and_send_otp(user, purpose)
            
            if result['success']:
                # Set cooldown
                RedisOTPManager.increment_resend_count(user_id)
                
                return {
                    'success': True,
                    'message': 'Mã OTP mới đã được gửi đến email của bạn.',
                    'remaining_seconds': 60  # 1 minute cooldown
                }
            else:
                return result
                
        except User.DoesNotExist:
            return {
                'success': False,
                'message': 'Người dùng không tồn tại.'
            }
        except Exception as e:
            logger.error(f"Failed to resend OTP for user {user_id}: {str(e)}")
            return {
                'success': False,
                'message': 'Có lỗi khi gửi lại mã OTP. Vui lòng thử lại.'
            }
    
    @staticmethod
    def get_remaining_cooldown(user_id: int) -> int:
        """Get remaining cooldown time in seconds"""
        return RedisOTPManager.get_remaining_time(user_id)
