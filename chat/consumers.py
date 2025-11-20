import json
import logging
from typing import Dict
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.db import models
from core.models import CustomUser
from .models import Message
from .bot import OrderBot
from .gemini_service import get_gemini_service
from .context_manager import ConversationContextManager

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
except ImportError:
    genai = None

class PrivateChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = self.room_name

        user = self.scope['user']
        if not user.is_authenticated:
            await self.close()
            return

        try: 
            _, id1_str, id2_str = self.room_name.split('_')
            id1, id2 = int(id1_str), int(id2_str)
        except ValueError:
            await self.close()
            return

        if user.user_id not in [id1, id2]:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        user = self.scope['user']
        username = user.full_name or user.phone_number or 'Người dùng'
        sender_id = user.user_id

        # Lưu tin nhắn vào database
        await self.save_message_to_db(message, sender_id)

        # ✅ GỬI TIN NHẮN CHỈ ĐẾN USER KHÁC
        # Lấy danh sách user trong room
        _, id1_str, id2_str = self.room_name.split('_')
        id1, id2 = int(id1_str), int(id2_str)
        
        # Tìm user khác (không phải người gửi)
        other_user_id = id1 if sender_id == id2 else id2

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'username': username,
                'sender_id': sender_id,
                'target_user_id': other_user_id,
            }
        )

    async def chat_message(self, event):
        current_user_id = self.scope['user'].user_id
        sender_id = event.get('sender_id')
        
        # Send message to all users in the room (both sender and recipient will receive it)
        # The frontend will filter to only show messages from others
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'username': event['username'],
            'sender_id': sender_id
        }))

    @sync_to_async
    def save_message_to_db(self, content, sender_id):
        """Lưu tin nhắn vào database"""
        try:
            # Lấy thông tin sender và recipient
            sender = CustomUser.objects.get(user_id=sender_id)
            
            # Lấy danh sách user trong room để tìm recipient
            _, id1_str, id2_str = self.room_name.split('_')
            id1, id2 = int(id1_str), int(id2_str)
            
            # Tìm recipient (user khác trong room)
            recipient_id = id1 if sender_id == id2 else id2
            recipient = CustomUser.objects.get(user_id=recipient_id)
            
            # Tạo tin nhắn mới
            Message.objects.create(
                sender=sender,
                recipient=recipient,
                content=content,
                room_name=self.room_name
            )
        except Exception as e:
            print(f"Lỗi khi lưu tin nhắn: {e}")


class OrderBotConsumer(AsyncWebsocketConsumer):
    """Consumer cho chatbot đặt hàng với Google Gemini AI"""
    
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = self.room_name
        
        user = self.scope['user']
        logger.info(f"OrderBotConsumer connect attempt - User: {user.user_id}, Room: {self.room_name}")
        
        if not user.is_authenticated:
            logger.warning("User not authenticated, closing connection")
            await self.close()
            return
        
        # Kiểm tra room có phải là chat với bot không
        is_bot_room = await sync_to_async(OrderBot.is_bot_room)(self.room_name)
        logger.info(f"Is bot room: {is_bot_room}")
        
        if not is_bot_room:
            logger.warning(f"Room {self.room_name} is not a bot room, closing connection")
            await self.close()
            return
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )
        await self.accept()
        logger.info(f"OrderBotConsumer connected successfully for room {self.room_name}")
        
        # Gửi lời chào ban đầu nếu chưa có tin nhắn nào
        await self.send_welcome_if_needed(user)
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )
    
    async def receive(self, text_data):
        print(f"\n{'='*60}")
        print(f"📨 OrderBotConsumer RECEIVED MESSAGE")
        print(f"   Raw data: {text_data}")
        print(f"{'='*60}\n")
        
        logger.info(f"OrderBotConsumer received message: {text_data}")
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        user = self.scope['user']
        
        print(f"   User: {user.user_id}")
        print(f"   Message: {message}")
        logger.info(f"Processing message from user {user.user_id}: {message}")
        
        # Lưu tin nhắn của user
        await sync_to_async(ConversationContextManager.save_message)(
            user.user_id, message, is_bot=False
        )
        
        # Lưu vào database
        await self.save_message_to_db(message, user.user_id, is_bot=False)
        
        # Lấy conversation history và user context
        history = await sync_to_async(ConversationContextManager.get_conversation_history)(
            user.user_id
        )
        user_context = await sync_to_async(ConversationContextManager.get_user_context)(user)
        mentioned_product = await sync_to_async(ConversationContextManager.get_mentioned_product)(user.user_id)
        
        # If mentioned product has variants, get variants info for context
        if mentioned_product:
            product_id = mentioned_product.get('product_id')
            if product_id:
                variants_info = await sync_to_async(self._get_product_variants_sync)(product_id, user)
                if variants_info.get('success'):
                    mentioned_product['variants'] = variants_info.get('variants', [])
        
        logger.info(f"User context: {user_context}, History length: {len(history)}")
        if mentioned_product:
            logger.info(f"Mentioned product: {mentioned_product.get('product_name')} (ID: {mentioned_product.get('product_id')})")
        
        # Xử lý với Gemini AI
        response_text = None
        try:
            gemini_service = get_gemini_service()
            logger.info(f"Gemini service obtained, model available: {gemini_service.model is not None}")
            
            if not gemini_service.model:
                logger.warning("Gemini model not available, using fallback")
                response_text = f"Hello! I can help you search for products, view your cart, and place orders. What would you like to do?"
            else:
                # Create a wrapper function executor that can be called from sync context
                # Since process_message runs in sync context (via sync_to_async), we need to handle async executor
                import asyncio
                
                # Store reference to self for use in executor
                consumer_self = self
                
                def sync_function_executor(function_call_dict):
                    """Wrapper to execute functions from sync context by calling sync methods directly"""
                    logger.info(f"🔧 sync_function_executor called for: {function_call_dict.get('name')}")
                    
                    function_name = function_call_dict.get('name')
                    arguments = function_call_dict.get('arguments', {})
                    user = consumer_self.scope['user']
                    
                    try:
                        # Call sync methods directly instead of going through async execute_function
                        # This avoids the deadlock issue with sync_to_async
                        if function_name == 'search_products':
                            query = arguments.get('query')
                            if not query or not str(query).strip():
                                return {'success': False, 'error': 'Search query is required'}
                            return consumer_self._search_products_sync(str(query).strip(), user)
                            
                        elif function_name == 'get_cart':
                            return consumer_self._get_cart_sync(user)
                            
                        elif function_name == 'add_to_cart':
                            product_id = arguments.get('product_id')
                            if not product_id:
                                return {'success': False, 'error': 'Product ID is required'}
                            try:
                                product_id = int(product_id)
                            except (ValueError, TypeError):
                                return {'success': False, 'error': 'Invalid product ID'}
                            quantity = arguments.get('quantity', 1)
                            try:
                                quantity = int(quantity) if quantity else 1
                                if quantity < 1:
                                    quantity = 1
                            except (ValueError, TypeError):
                                quantity = 1
                            variant_id = arguments.get('variant_id')
                            if variant_id:
                                try:
                                    variant_id = int(variant_id)
                                except (ValueError, TypeError):
                                    variant_id = None
                            return consumer_self._add_to_cart_sync(product_id, quantity, user, variant_id)
                        
                        elif function_name == 'get_product_variants':
                            product_id = arguments.get('product_id')
                            if not product_id:
                                return {'success': False, 'error': 'Product ID is required'}
                            try:
                                product_id = int(product_id)
                            except (ValueError, TypeError):
                                return {'success': False, 'error': 'Invalid product ID'}
                            return consumer_self._get_product_variants_sync(product_id, user)
                            
                        elif function_name == 'create_order':
                            return consumer_self._create_order_sync(user)
                            
                        elif function_name == 'get_orders':
                            limit = arguments.get('limit', 5)
                            try:
                                limit = int(limit) if limit else 5
                                if limit < 1 or limit > 20:
                                    limit = 5
                            except (ValueError, TypeError):
                                limit = 5
                            return consumer_self._get_orders_sync(limit, user)
                            
                        elif function_name == 'get_product_details':
                            product_id = arguments.get('product_id')
                            if not product_id:
                                return {'success': False, 'error': 'Product ID is required'}
                            try:
                                product_id = int(product_id)
                            except (ValueError, TypeError):
                                return {'success': False, 'error': 'Invalid product ID'}
                            return consumer_self._get_product_details_sync(product_id, user)
                            
                        else:
                            return {'success': False, 'error': f'Unknown function: {function_name}'}
                            
                    except Exception as e:
                        logger.error(f"❌ Error in sync_function_executor: {str(e)}", exc_info=True)
                        return {'success': False, 'error': f'Executor error: {str(e)}'}
                
                # Process message with Gemini, passing function executor
                # Gemini will handle function calling internally and generate natural responses
                logger.info("Calling Gemini API with function calling support...")
                result = await sync_to_async(gemini_service.process_message)(
                    user_message=message,
                    conversation_history=history,
                    user_context=user_context,
                    mentioned_product=mentioned_product,
                    function_executor=sync_function_executor
                )
                
                logger.info(f"Gemini result received: {result}")
                response_text = result.get('response', 'Sorry, I cannot process this request.')
                
                # Handle function execution results and update context
                function_result = result.get('function_result')
                if function_result and result.get('function_call'):
                    function_name = result['function_call'].get('name')
                    
                    # Save mentioned product after search
                    if function_name == 'search_products' and function_result.get('success'):
                        products = function_result.get('products', [])
                        if products and len(products) > 0:
                            first_product = products[0]
                            product_id = first_product['product_id']
                            
                            # Get variants if product has variants
                            variants_data = None
                            if first_product.get('has_variants'):
                                variants_result = await sync_to_async(self._get_product_variants_sync)(product_id, user)
                                if variants_result.get('success'):
                                    variants_data = variants_result.get('variants', [])
                            
                            product_data = {
                                'product_id': product_id,
                                'product_name': first_product['name'],
                                'price': first_product['price'],
                                'store_name': first_product.get('store_name', 'N/A')
                            }
                            if variants_data:
                                product_data['variants'] = variants_data
                            
                            await sync_to_async(ConversationContextManager.save_mentioned_product)(
                                user.user_id,
                                product_data
                            )
                            logger.info(f"Saved mentioned product: {first_product['name']} with {len(variants_data) if variants_data else 0} variants")
                    
                    # Clear mentioned product after adding to cart or creating order
                    elif function_name in ['add_to_cart', 'create_order']:
                        await sync_to_async(ConversationContextManager.clear_mentioned_product)(user.user_id)
                        logger.info(f"Cleared mentioned product after {function_name}")
                    
                    # Handle function errors with user-friendly messages
                    if not function_result.get('success'):
                        error_msg = function_result.get('error', 'Unknown error')
                        logger.warning(f"Function {function_name} failed: {error_msg}")
                        
                        # Special handling for products with variants - don't override response
                        # The response already contains variant information from _generate_response_from_function_result
                        if function_name == 'add_to_cart' and function_result.get('has_variants'):
                            # Response already contains variant list, keep it
                            logger.info("Product has variants, keeping variant information in response")
                            pass
                        else:
                            # Generate user-friendly error messages based on function type
                            user_friendly_errors = {
                                'search_products': "I couldn't find any products matching your search. Could you try different keywords?",
                                'add_to_cart': f"I couldn't add that item to your cart. {error_msg}",
                                'get_cart': "I couldn't retrieve your cart. Please try again.",
                                'create_order': f"I couldn't create your order. {error_msg}",
                                'get_orders': "I couldn't retrieve your orders. Please try again.",
                                'get_product_details': f"I couldn't get the product details. {error_msg}"
                            }
                            
                            # Use Gemini's response if available, otherwise use friendly error message
                            if response_text and 'error' in response_text.lower():
                                # Gemini already provided an error response, use it
                                pass
                            else:
                                # Use friendly error message
                                friendly_msg = user_friendly_errors.get(function_name, f"I encountered an issue: {error_msg}. Please try again.")
                                response_text = friendly_msg
                
                if not response_text or len(response_text.strip()) == 0:
                    logger.warning("Empty response from Gemini, using fallback")
                    response_text = f"I received your message: '{message}'. How can I help you?"
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            response_text = f"Sorry, I encountered an error processing your request. Error: {str(e)}. Please try again."
        
        # Ensure we have a response
        if not response_text:
            response_text = f"I received your message: '{message}'. What would you like to do?"
        
        logger.info(f"Final response text: {response_text}")
        logger.info(f"Response length: {len(response_text)}")
        
        # Gửi phản hồi từ bot
        try:
            await self.send_bot_message(response_text)
            logger.info("Bot message sent to WebSocket")
        except Exception as e:
            logger.error(f"Failed to send bot message: {str(e)}", exc_info=True)
        
        # Lưu tin nhắn bot vào context và database
        await sync_to_async(ConversationContextManager.save_message)(
            user.user_id, response_text, is_bot=True
        )
        await self.save_message_to_db(response_text, None, is_bot=True)
        
        logger.info("Message processing completed")
    
    async def send_welcome_if_needed(self, user):
        """Gửi lời chào nếu chưa có tin nhắn nào"""
        from .models import Message
        
        bot_user = await sync_to_async(OrderBot.get_or_create_bot_user)()
        messages_count = await sync_to_async(Message.objects.filter(
            room_name=self.room_name
        ).count)()
        
        if messages_count == 0:
            welcome_msg = (
                "👋 Hello! I'm your order assistance chatbot.\n\n"
                "I can help you with:\n"
                "🔍 Search for products (e.g., 'find potatoes')\n"
                "🛒 View your cart (type 'cart')\n"
                "➕ Add products to cart (e.g., 'add product 1')\n"
                "📦 Place an order (type 'checkout' or 'place order')\n"
                "📋 View your orders (type 'orders')\n"
                "❓ Get help (type 'help')"
            )
            await self.send_bot_message(welcome_msg)
            await self.save_message_to_db(welcome_msg, None, is_bot=True)
    
    async def execute_function(self, function_call: Dict) -> Dict:
        """Execute a function call from Gemini with comprehensive error handling"""
        function_name = function_call.get('name')
        arguments = function_call.get('arguments', {})
        
        if not function_name:
            return {'success': False, 'error': 'Function name is required'}
        
        user = self.scope['user']
        
        logger.info(f"Executing function: {function_name} with arguments: {arguments}")
        
        try:
            if function_name == 'search_products':
                query = arguments.get('query')
                if not query or not str(query).strip():
                    return {'success': False, 'error': 'Search query is required'}
                return await self._search_products(str(query).strip(), user)
            
            elif function_name == 'get_cart':
                return await self._get_cart(user)
            
            elif function_name == 'add_to_cart':
                product_id = arguments.get('product_id')
                if not product_id:
                    return {'success': False, 'error': 'Product ID is required'}
                try:
                    product_id = int(product_id)
                except (ValueError, TypeError):
                    return {'success': False, 'error': 'Invalid product ID'}
                
                quantity = arguments.get('quantity', 1)
                try:
                    quantity = int(quantity) if quantity else 1
                    if quantity < 1:
                        quantity = 1
                except (ValueError, TypeError):
                    quantity = 1
                
                variant_id = arguments.get('variant_id')
                if variant_id:
                    try:
                        variant_id = int(variant_id)
                    except (ValueError, TypeError):
                        variant_id = None
                
                return await self._add_to_cart(product_id, quantity, user, variant_id)
            
            elif function_name == 'get_product_variants':
                product_id = arguments.get('product_id')
                if not product_id:
                    return {'success': False, 'error': 'Product ID is required'}
                try:
                    product_id = int(product_id)
                except (ValueError, TypeError):
                    return {'success': False, 'error': 'Invalid product ID'}
                return await self._get_product_variants(product_id, user)
            
            elif function_name == 'create_order':
                return await self._create_order(user)
            
            elif function_name == 'get_orders':
                limit = arguments.get('limit', 5)
                try:
                    limit = int(limit) if limit else 5
                    if limit < 1 or limit > 20:
                        limit = 5
                except (ValueError, TypeError):
                    limit = 5
                return await self._get_orders(limit, user)
            
            elif function_name == 'get_product_details':
                product_id = arguments.get('product_id')
                if not product_id:
                    return {'success': False, 'error': 'Product ID is required'}
                try:
                    product_id = int(product_id)
                except (ValueError, TypeError):
                    return {'success': False, 'error': 'Invalid product ID'}
                return await self._get_product_details(product_id, user)
            
            else:
                logger.warning(f"Unknown function requested: {function_name}")
                return {'success': False, 'error': f'Unknown function: {function_name}'}
        
        except Exception as e:
            logger.error(f"Error executing function {function_name}: {str(e)}", exc_info=True)
            # Provide user-friendly error messages
            error_message = str(e)
            if 'DoesNotExist' in error_message:
                error_message = 'The requested item was not found'
            elif 'IntegrityError' in error_message:
                error_message = 'There was a problem saving your data. Please try again.'
            elif 'ValidationError' in error_message:
                error_message = 'Invalid data provided. Please check your input.'
            return {'success': False, 'error': error_message}
    
    def _search_products_sync(self, query: str, user):
        """Sync version of search_products for use in sync context"""
        from core.models import Product
        
        if not query or not query.strip():
            logger.warning(f"Empty query received in _search_products_sync")
            return {'success': False, 'error': 'Query is required'}
        
        # Clean and normalize query
        query = query.strip().lower()  # Normalize to lowercase for better matching
        logger.info(f"🔍 Searching products with query: '{query}'")
        
        # Try exact match first, then partial match
        products = Product.objects.filter(
            is_active=True
        ).filter(
            models.Q(name__icontains=query) | 
            models.Q(description__icontains=query)
        )[:10]
        
        logger.info(f"🔍 Database query returned {products.count()} products")
        
        products_data = []
        for p in products:
            products_data.append({
                'product_id': p.product_id,
                'name': p.name,
                'price': float(p.price),
                'store_name': p.store.store_name,
                'has_variants': p.has_variants,
            })
            logger.debug(f"  - Found: {p.name} (ID: {p.product_id})")
        
        logger.info(f"✅ Found {len(products_data)} products for query '{query}'")
        
        # Save the first product as mentioned product for context
        if products_data and len(products_data) > 0:
            first_product = products_data[0]
            ConversationContextManager.save_mentioned_product(
                user.user_id,
                {
                    'product_id': first_product['product_id'],
                    'product_name': first_product['name'],
                    'price': first_product['price'],
                    'store_name': first_product.get('store_name', 'N/A')
                }
            )
            logger.info(f"Saved mentioned product: {first_product['name']} (ID: {first_product['product_id']})")
        
        return {
            'success': True,
            'products': products_data,
            'count': len(products_data),
            'query': query  # Include query in response for debugging
        }
    
    @sync_to_async
    def _search_products(self, query: str, user):
        """Async version of search_products"""
        return self._search_products_sync(query, user)
    
    def _get_cart_sync(self, user):
        """Sync version of get_cart for use in sync context"""
        from core.models import CartItem
        
        cart_items = CartItem.objects.filter(user=user).select_related('product', 'variant')
        
        items_data = []
        total = 0
        
        for item in cart_items:
            item_total = float(item.total_price)
            total += item_total
            items_data.append({
                'product_id': item.product.product_id,
                'product_name': item.product.name,
                'variant_name': item.variant.variant_name if item.variant else None,
                'quantity': item.quantity,
                'unit_price': float(item.unit_price),
                'total_price': item_total,
            })
        
        return {
            'success': True,
            'items': items_data,
            'total': total,
            'count': len(items_data)
        }
    
    @sync_to_async
    def _get_cart(self, user):
        """Async version of get_cart"""
        return self._get_cart_sync(user)
    
    def _get_product_variants_sync(self, product_id: int, user):
        """Sync version of get_product_variants for use in sync context"""
        from core.models import Product, ProductVariant
        
        try:
            product = Product.objects.get(product_id=product_id, is_active=True)
        except Product.DoesNotExist:
            return {'success': False, 'error': f'Product {product_id} not found'}
        
        if not product.has_variants:
            return {'success': False, 'error': 'Product does not have variants'}
        
        variants = ProductVariant.objects.filter(
            product=product,
            is_active=True
        ).order_by('sort_order', 'price')
        
        variants_data = []
        for v in variants:
            variants_data.append({
                'variant_id': v.variant_id,
                'variant_name': v.variant_name,
                'price': float(v.price),
                'stock': v.stock,
                'is_in_stock': v.stock > 0,
            })
        
        return {
            'success': True,
            'product_id': product_id,
            'product_name': product.name,
            'variants': variants_data,
            'count': len(variants_data)
        }
    
    @sync_to_async
    def _get_product_variants(self, product_id: int, user):
        """Async version of get_product_variants"""
        return self._get_product_variants_sync(product_id, user)
    
    def _add_to_cart_sync(self, product_id: int, quantity: int, user, variant_id: int = None):
        """Sync version of add_to_cart for use in sync context"""
        from core.models import Product, ProductVariant, CartItem
        
        logger.info(f"🛒 _add_to_cart_sync called: product_id={product_id}, quantity={quantity}, variant_id={variant_id}, user={user.user_id}")
        
        auto_selected_variant = False
        
        try:
            product = Product.objects.get(product_id=product_id, is_active=True)
            logger.info(f"✅ Product found: {product.name}")
        except Product.DoesNotExist:
            logger.error(f"❌ Product {product_id} not found")
            return {'success': False, 'error': f'Product {product_id} not found'}
        
        variant = None
        if product.has_variants:
            if not variant_id:
                logger.warning(f"⚠️ Product {product_id} has variants but no variant_id provided")
                # Get variants to show user and auto-select first variant as default
                variants_result = self._get_product_variants_sync(product_id, user)
                if variants_result.get('success'):
                    variants = variants_result.get('variants', [])
                    if variants:
                        # Auto-select first available variant (default behavior)
                        first_variant = variants[0]
                        variant_id = first_variant['variant_id']
                        auto_selected_variant = True
                        logger.info(f"✅ Auto-selecting first variant: {first_variant['variant_name']} (ID: {variant_id})")
                        # Continue to add variant below
                    else:
                        return {
                            'success': False,
                            'error': 'Product has variants but none are available.',
                            'product_id': product_id
                        }
                else:
                    return {
                        'success': False,
                        'error': 'Product has variants. Please specify a variant.',
                        'product_id': product_id
                    }
            
            try:
                variant = ProductVariant.objects.get(
                    variant_id=variant_id,
                    product=product,
                    is_active=True
                )
                logger.info(f"✅ Variant found: {variant.variant_name}")
                
                # Check stock
                if variant.stock < quantity:
                    return {
                        'success': False,
                        'error': f'Insufficient stock. Available: {variant.stock}',
                        'product_id': product_id,
                        'variant_id': variant_id
                    }
            except ProductVariant.DoesNotExist:
                logger.warning(f"⚠️ Variant {variant_id} not found for product {product_id}, trying to match by name")
                # Try to find variant by matching variant_id with variant_name or by searching variants
                # This handles cases where Gemini misunderstood variant_id (e.g., user said "3 bunches" but Gemini used variant_id=3)
                variants_result = self._get_product_variants_sync(product_id, user)
                if variants_result.get('success'):
                    variants = variants_result.get('variants', [])
                    # Try to find variant where variant_id matches or variant_name contains the number
                    matched_variant = None
                    for v in variants:
                        # Check if variant_id matches
                        if v['variant_id'] == variant_id:
                            matched_variant = v
                            break
                        # Check if variant_name contains the variant_id as a number (e.g., "3 bunches" contains "3")
                        if str(variant_id) in v['variant_name'].lower():
                            matched_variant = v
                            logger.info(f"✅ Matched variant by name: {v['variant_name']} (ID: {v['variant_id']})")
                            break
                    
                    if matched_variant:
                        variant_id = matched_variant['variant_id']
                        variant = ProductVariant.objects.get(
                            variant_id=variant_id,
                            product=product,
                            is_active=True
                        )
                        logger.info(f"✅ Using matched variant: {variant.variant_name} (ID: {variant_id})")
                    else:
                        logger.error(f"❌ Could not match variant {variant_id} for product {product_id}")
                        return {
                            'success': False,
                            'error': f'Variant not found. Available variants: {", ".join([v["variant_name"] for v in variants])}',
                            'product_id': product_id,
                            'has_variants': True,
                            'variants': variants
                        }
                else:
                    logger.error(f"❌ Variant {variant_id} not found for product {product_id}")
                    return {'success': False, 'error': f'Variant {variant_id} not found'}
        
        try:
            cart_item, created = CartItem.objects.get_or_create(
                user=user,
                product=product,
                variant=variant,
                defaults={'quantity': quantity}
            )
            
            if not created:
                cart_item.quantity += quantity
                cart_item.save()
                logger.info(f"✅ Updated existing cart item: quantity={cart_item.quantity}")
            else:
                logger.info(f"✅ Created new cart item: quantity={cart_item.quantity}")
            
            # Verify the cart item was saved
            verify_item = CartItem.objects.filter(
                user=user,
                product=product,
                variant=variant
            ).first()
            if verify_item:
                logger.info(f"✅ Verified cart item exists: product_id={verify_item.product.product_id}, quantity={verify_item.quantity}")
            else:
                logger.error(f"❌ Cart item verification failed!")
            
            variant_name_str = f" ({variant.variant_name})" if variant else ""
            result = {
                'success': True,
                'product_name': product.name,
                'variant_name': variant.variant_name if variant else None,
                'quantity': cart_item.quantity,
                'product_id': product_id,
                'variant_id': variant_id if variant else None
            }
            # If variant was auto-selected, add flag for response generation
            if auto_selected_variant:
                result['auto_selected_variant'] = True
            return result
        except Exception as e:
            logger.error(f"❌ Error adding to cart: {str(e)}", exc_info=True)
            return {'success': False, 'error': f'Failed to add product to cart: {str(e)}'}
    
    @sync_to_async
    def _add_to_cart(self, product_id: int, quantity: int, user, variant_id: int = None):
        """Async version of add_to_cart"""
        return self._add_to_cart_sync(product_id, quantity, user, variant_id)
    
    def _create_order_sync(self, user):
        """Sync version of create_order for use in sync context"""
        from core.models import CartItem, Order, OrderItem, Address
        
        cart_items = CartItem.objects.filter(user=user).select_related('product', 'variant')
        
        if not cart_items.exists():
            return {'success': False, 'error': 'Cart is empty'}
        
        addresses = Address.objects.filter(user=user, is_default=True)
        if not addresses.exists():
            return {'success': False, 'error': 'No shipping address'}
        
        shipping_address = addresses.first()
        
        from collections import defaultdict
        stores_dict = defaultdict(list)
        for item in cart_items:
            stores_dict[item.product.store].append(item)
        
        orders_created = []
        total = 0
        
        for store, items in stores_dict.items():
            subtotal = sum(float(item.total_price) for item in items)
            shipping_cost = 30000
            order_total = subtotal + shipping_cost
            total += order_total
            
            order = Order.objects.create(
                user=user,
                shipping_address=shipping_address,
                subtotal=subtotal,
                shipping_cost=shipping_cost,
                total_amount=order_total,
                payment_method='cod',
                status='pending'
            )
            
            for item in items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    variant=item.variant,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    total_price=item.total_price
                )
            
            CartItem.objects.filter(user=user, product__store=store).delete()
            orders_created.append(order.order_id)
        
        return {
            'success': True,
            'order_ids': orders_created,
            'total': total
        }
    
    @sync_to_async
    def _create_order(self, user):
        """Async version of create_order"""
        return self._create_order_sync(user)
    
    def _get_orders_sync(self, limit: int, user):
        """Sync version of get_orders for use in sync context"""
        from core.models import Order
        
        orders = Order.objects.filter(user=user).order_by('-created_at')[:limit]
        
        orders_data = []
        for order in orders:
            orders_data.append({
                'order_id': order.order_id,
                'status': order.status,
                'status_display': order.get_status_display(),
                'total_amount': float(order.total_amount),
                'created_at': order.created_at.isoformat(),
            })
        
        return {
            'success': True,
            'orders': orders_data,
            'count': len(orders_data)
        }
    
    @sync_to_async
    def _get_orders(self, limit: int, user):
        """Async version of get_orders"""
        return self._get_orders_sync(limit, user)
    
    def _get_product_details_sync(self, product_id: int, user):
        """Sync version of get_product_details for use in sync context"""
        from core.models import Product
        
        try:
            product = Product.objects.get(product_id=product_id, is_active=True)
            return {
                'success': True,
                'product': {
                    'product_id': product.product_id,
                    'name': product.name,
                    'description': product.description,
                    'price': float(product.price),
                    'store_name': product.store.store_name,
                    'has_variants': product.has_variants,
                }
            }
        except Product.DoesNotExist:
            return {'success': False, 'error': f'Product {product_id} not found'}
    
    @sync_to_async
    def _get_product_details(self, product_id: int, user):
        """Async version of get_product_details"""
        return self._get_product_details_sync(product_id, user)
    
    async def send_bot_message(self, content):
        """Gửi tin nhắn từ bot"""
        try:
            bot_user = await sync_to_async(OrderBot.get_or_create_bot_user)()
            
            message_data = {
                'message': content,
                'username': OrderBot.BOT_DISPLAY_NAME,
                'sender_id': bot_user.user_id,
                'is_bot': True
            }
            
            logger.info(f"Sending bot message: {json.dumps(message_data)}")
            
            # Gửi qua WebSocket
            await self.send(text_data=json.dumps(message_data))
            
            logger.info("Bot message sent successfully")
        except Exception as e:
            logger.error(f"Error sending bot message: {str(e)}", exc_info=True)
            # Thử gửi lại với format đơn giản
            try:
                await self.send(text_data=json.dumps({
                    'message': content,
                    'username': 'Bot',
                    'sender_id': 0,
                }))
            except Exception as e2:
                logger.error(f"Failed to send fallback message: {str(e2)}")
    
    @sync_to_async
    def save_message_to_db(self, content, sender_id, is_bot=False):
        """Lưu tin nhắn vào database"""
        try:
            if is_bot:
                sender = OrderBot.get_or_create_bot_user()
            else:
                sender = CustomUser.objects.get(user_id=sender_id)
            
            user = self.scope['user']
            
            # Xác định recipient
            if is_bot:
                recipient = user
            else:
                recipient = OrderBot.get_or_create_bot_user()
            
            Message.objects.create(
                sender=sender,
                recipient=recipient,
                content=content,
                room_name=self.room_name
            )
        except Exception as e:
            logger.error(f"Lỗi khi lưu tin nhắn: {e}")

        