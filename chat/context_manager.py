"""
Context Manager để lưu trữ conversation history và user context
"""
import json
import logging
from typing import List, Dict, Optional
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class ConversationContextManager:
    """Quản lý context của conversation"""
    
    CACHE_PREFIX = 'chatbot:conversation:'
    CACHE_TTL = 3600 * 24  # 24 hours
    
    @classmethod
    def get_conversation_key(cls, user_id: int) -> str:
        """Tạo cache key cho conversation"""
        return f"{cls.CACHE_PREFIX}{user_id}"
    
    @classmethod
    def save_message(cls, user_id: int, message: str, is_bot: bool = False):
        """Lưu tin nhắn vào conversation history"""
        try:
            key = cls.get_conversation_key(user_id)
            history = cls.get_conversation_history(user_id)
            
            history.append({
                'content': message,
                'is_bot': is_bot,
                'timestamp': str(timezone.now())
            })
            
            # Chỉ giữ 20 tin nhắn gần nhất
            history = history[-20:]
            
            cache.set(key, json.dumps(history), cls.CACHE_TTL)
        except Exception as e:
            logger.error(f"Error saving message: {str(e)}")
    
    @classmethod
    def get_conversation_history(cls, user_id: int) -> List[Dict]:
        """Lấy conversation history"""
        try:
            key = cls.get_conversation_key(user_id)
            cached = cache.get(key)
            if cached:
                return json.loads(cached)
            return []
        except Exception as e:
            logger.error(f"Error getting conversation history: {str(e)}")
            return []
    
    @classmethod
    def clear_conversation(cls, user_id: int):
        """Xóa conversation history"""
        try:
            key = cls.get_conversation_key(user_id)
            cache.delete(key)
        except Exception as e:
            logger.error(f"Error clearing conversation: {str(e)}")
    
    @classmethod
    def get_user_context(cls, user) -> Dict:
        """Lấy user context (cart, orders, etc.)"""
        from core.models import CartItem, Order
        
        try:
            cart_items_count = CartItem.objects.filter(user=user).count()
            recent_orders_count = Order.objects.filter(user=user).count()
            
            return {
                'full_name': user.full_name or 'Customer',
                'cart_items_count': cart_items_count,
                'recent_orders_count': recent_orders_count,
            }
        except Exception as e:
            logger.error(f"Error getting user context: {str(e)}")
            return {}
    
    @classmethod
    def save_mentioned_product(cls, user_id: int, product_data: Dict):
        """Lưu sản phẩm đã được đề cập trong conversation
        
        Args:
            user_id: User ID
            product_data: Dict với keys: product_id, product_name, price (optional), store_name (optional)
        """
        try:
            key = f"{cls.CACHE_PREFIX}{user_id}:mentioned_product"
            product_info = {
                'product_id': product_data.get('product_id'),
                'product_name': product_data.get('product_name'),
                'price': product_data.get('price', 0),
                'store_name': product_data.get('store_name', 'N/A'),
                'timestamp': str(timezone.now())
            }
            cache.set(key, json.dumps(product_info), cls.CACHE_TTL)
            logger.debug(f"Saved mentioned product for user {user_id}: {product_info.get('product_name')}")
        except Exception as e:
            logger.error(f"Error saving mentioned product: {str(e)}")
    
    @classmethod
    def get_mentioned_product(cls, user_id: int) -> Optional[Dict]:
        """Lấy sản phẩm đã được đề cập gần nhất"""
        try:
            key = f"{cls.CACHE_PREFIX}{user_id}:mentioned_product"
            cached = cache.get(key)
            if cached:
                product_data = json.loads(cached)
                logger.debug(f"Retrieved mentioned product for user {user_id}: {product_data.get('product_name')}")
                return product_data
            return None
        except Exception as e:
            logger.error(f"Error getting mentioned product: {str(e)}")
            return None
    
    @classmethod
    def clear_mentioned_product(cls, user_id: int):
        """Xóa sản phẩm đã được đề cập gần nhất"""
        try:
            key = f"{cls.CACHE_PREFIX}{user_id}:mentioned_product"
            cache.delete(key)
            logger.debug(f"Cleared mentioned product for user {user_id}")
        except Exception as e:
            logger.error(f"Error clearing mentioned product: {str(e)}")

