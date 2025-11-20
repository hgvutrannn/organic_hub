"""
Bot helper utilities
"""
from core.models import CustomUser
from django.db import transaction

class OrderBot:
    """Order assistance chatbot"""
    BOT_USERNAME = "order_bot"
    BOT_DISPLAY_NAME = "Order Assistant Bot"
    
    @classmethod
    def get_or_create_bot_user(cls):
        """Lấy hoặc tạo bot user"""
        bot_user, created = CustomUser.objects.get_or_create(
            phone_number=cls.BOT_USERNAME,
            defaults={
                'full_name': cls.BOT_DISPLAY_NAME,
                'is_active': True,
            }
        )
        return bot_user
    
    @classmethod
    def get_bot_room_name(cls, user_id):
        """Tạo room name cho chat với bot"""
        bot_user = cls.get_or_create_bot_user()
        user_ids = sorted([bot_user.user_id, user_id])
        return f"chat_{user_ids[0]}_{user_ids[1]}"
    
    @classmethod
    def is_bot_room(cls, room_name):
        """Kiểm tra xem room có phải là chat với bot không"""
        try:
            bot_user = cls.get_or_create_bot_user()
            _, id1_str, id2_str = room_name.split('_')
            id1, id2 = int(id1_str), int(id2_str)
            return bot_user.user_id in [id1, id2]
        except (ValueError, AttributeError):
            return False
    
    @classmethod
    def create_welcome_message(cls, user):
        """Tạo tin nhắn chào mừng từ bot"""
        from .models import Message
        
        bot_user = cls.get_or_create_bot_user()
        room_name = cls.get_bot_room_name(user.user_id)
        
        welcome_content = (
            "👋 Hello! I'm your order assistance chatbot.\n\n"
            "I can help you with:\n"
            "🔍 Search for products (e.g., 'find potatoes')\n"
            "🛒 View your cart (type 'cart')\n"
            "➕ Add products to cart (e.g., 'add product 1')\n"
            "📦 Place an order (type 'checkout' or 'place order')\n"
            "📋 View your orders (type 'orders')\n"
            "❓ Get help (type 'help')"
        )
        
        Message.objects.create(
            sender=bot_user,
            recipient=user,
            content=welcome_content,
            room_name=room_name,
            is_read=False
        )

