from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth import get_user_model
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_otp_email_task(self, user_id: int, otp_code: str, purpose: str = 'registration'):
    """
    Async task to send OTP email via AWS SES
    - Load user from database
    - Compose HTML email from template
    - Send via Django's send_mail with AWS SES backend
    - Handle exceptions with exponential backoff retry
    - Log success/failure
    """
    try:
        # Load user from database
        user = User.objects.get(user_id=user_id)
        
        # Prepare email context
        context = {
            'user': user,
            'otp_code': otp_code,
            'purpose': purpose,
            'expiry_minutes': getattr(settings, 'OTP_EXPIRY_MINUTES', 5),
        }
        
        # Render email template
        subject = f"Mã xác thực OTP - {settings.DEFAULT_FROM_EMAIL}"
        html_message = render_to_string('otp_service/email/otp_email.html', context)
        
        # Send email via AWS SES
        send_mail(
            subject=subject,
            message=f"Mã OTP của bạn là: {otp_code}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        print(f"✅ OTP EMAIL SENT SUCCESSFULLY!")
        print(f"   📧 To: {user.email}")
        print(f"   👤 User: {user.full_name}")
        print(f"   🔢 OTP: {otp_code}")
        print("=" * 50)
        
        logger.info(f"OTP email sent successfully to {user.email} for user {user_id}")
        return f"OTP email sent successfully to {user.email}"
        
    except User.DoesNotExist:
        print(f"❌ ERROR: User with ID {user_id} not found")
        logger.error(f"User with ID {user_id} not found")
        return f"User with ID {user_id} not found"
        
    except Exception as exc:
        print(f"❌ ERROR SENDING OTP EMAIL:")
        print(f"   👤 User ID: {user_id}")
        print(f"   🚨 Error: {str(exc)}")
        print(f"   🔄 Retry attempt: {self.request.retries + 1}/3")
        print("=" * 50)
        
        logger.error(f"Failed to send OTP email to user {user_id}: {str(exc)}")
        
        # Retry with exponential backoff
        countdown = 2 ** self.request.retries
        raise self.retry(exc=exc, countdown=countdown)
