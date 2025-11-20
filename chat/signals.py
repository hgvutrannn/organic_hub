"""
Django signals for chat app
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import CustomUser
from .bot import OrderBot
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CustomUser)
def create_bot_chat_room(sender, instance, created, **kwargs):
    """
    Tự động tạo phòng chat với bot khi user đăng ký
    """
    if created:
        try:
            # Tạo welcome message từ bot
            OrderBot.create_welcome_message(instance)
            logger.info(f"Created bot chat room for user {instance.user_id}")
        except Exception as e:
            logger.error(f"Error creating bot chat room for user {instance.user_id}: {str(e)}")

