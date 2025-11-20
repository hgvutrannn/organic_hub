"""
Google Gemini AI Service cho chatbot đặt hàng
"""
import os
import json
import logging
import re
from typing import Dict, List, Optional, Any
from django.conf import settings

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-generativeai not installed. Install with: pip install google-generativeai")


class GeminiAIService:
    """Service để tương tác với Google Gemini AI"""
    
    def __init__(self):
        if not GEMINI_AVAILABLE:
            logger.warning("google-generativeai package is not installed. Using fallback mode.")
            self.model = None
            return
        
        # Try to get API key from environment or settings
        api_key = os.getenv('GOOGLE_GEMINI_API_KEY') or getattr(settings, 'GOOGLE_GEMINI_API_KEY', None)
        if not api_key:
            logger.warning("GOOGLE_GEMINI_API_KEY not found in environment or settings. Using fallback mode.")
            self.model = None
            return
        
        try:
            logger.info(f"Initializing Gemini with API key: {api_key[:10]}...")
            genai.configure(api_key=api_key)
            # Use available models: gemini-2.0-flash (fast, free tier friendly) or gemini-flash-latest
            # Try gemini-2.0-flash first, fallback to gemini-flash-latest
            try:
                self.model = genai.GenerativeModel('gemini-2.0-flash')
                logger.info("Using model: gemini-2.0-flash")
            except Exception as e1:
                logger.warning(f"Failed to load gemini-2.0-flash: {e1}")
                try:
                    self.model = genai.GenerativeModel('gemini-flash-latest')
                    logger.info("Using model: gemini-flash-latest")
                except Exception as e2:
                    logger.warning(f"Failed to load gemini-flash-latest: {e2}")
                    try:
                        self.model = genai.GenerativeModel('gemini-2.5-flash')
                        logger.info("Using model: gemini-2.5-flash")
                    except Exception as e3:
                        logger.error(f"All model attempts failed: {e3}")
                        self.model = None
            if self.model:
                logger.info("Gemini model initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Gemini: {str(e)}", exc_info=True)
            self.model = None
    
    def build_system_prompt(self, user_context: Optional[Dict] = None, mentioned_product: Optional[Dict] = None) -> str:
        """Build system prompt with context"""
        base_prompt = """You are an intelligent order assistance chatbot for an organic food e-commerce website.

YOUR ROLE:
- Help users find and purchase organic food products
- Guide them through the shopping process: search → view details → add to cart → checkout
- Understand user intent from full conversation context, not just keywords
- Be conversational, friendly, and helpful

CONTEXT UNDERSTANDING:
- If user says "yes", "ok", "sure" after you asked about buying a product → they want to add it to cart
- If user says "it", "this", "that" → refer to the most recently mentioned product
- If user says "help me buy it" → guide them through: search → add to cart → checkout
- Remember conversation history to understand references

SHOPPING FLOW GUIDANCE:
When helping users buy products:
1. First, help them search for products if they haven't specified what they want
2. Show product details and help them add products to cart
3. Guide them to view their cart
4. Help them complete the checkout process

FUNCTION CALLING REQUIREMENTS:
- IMPORTANT: When user wants to perform an action (search, add to cart, checkout, etc.), you MUST call the appropriate function
- DO NOT just say you're doing something - actually call the function
- If user mentions ANY product name (e.g., "carrot", "potatoes", "apple") → you MUST call search_products function immediately
- Even single words like "carrot" or "apple" are product names and require searching - DO NOT respond with text only
- If user says "add it", "yes", "I want [product]", "add [product]" → you MUST call add_to_cart function with product_id
- When calling add_to_cart, you can optionally include variant_id if user specified a variant (e.g., "1kg", "smallest", "cheapest", variant name)
- If add_to_cart fails because product has variants → the system will automatically show variants, then you should help user select one
- If user describes a variant (e.g., "the 1kg one", "smallest", "cheapest", "first option") → try to match it with available variants and include variant_id
- If user doesn't specify variant but product has variants → call add_to_cart anyway, system will auto-select first variant
- If user wants to checkout → you MUST call create_order function
- After calling a function, you can then respond naturally about the result
- NEVER ask user for product ID - always use product names or "it"/"this" to refer to recently mentioned products

RESPONSE STYLE:
- Always respond in English in a natural and friendly manner
- Be conversational and helpful
- Guide users through the shopping process step by step
- Use appropriate emojis to make the conversation friendly
- Format prices: ${amount:,.2f} USD
- When you call a function, the system will execute it and then you can respond about the result
"""
        
        if user_context:
            context_info = f"""
USER CONTEXT:
- Name: {user_context.get('full_name', 'Customer')}
- Recent orders: {user_context.get('recent_orders_count', 0)}
- Items in cart: {user_context.get('cart_items_count', 0)}
"""
            base_prompt += context_info
        
        if mentioned_product:
            product_info = f"""
RECENTLY MENTIONED PRODUCT:
- Product ID: {mentioned_product.get('product_id')}
- Product Name: {mentioned_product.get('product_name')}
- Price: ${mentioned_product.get('price', 0):,.2f}
When user says "it", "this", or "that", they likely refer to this product.
"""
            # Add variants info if available
            variants = mentioned_product.get('variants', [])
            if variants:
                variants_list = "\n".join([
                    f"  - {v['variant_name']} (Variant ID: {v['variant_id']}) - ${v['price']:,.2f}"
                    for v in variants
                ])
                product_info += f"""
AVAILABLE VARIANTS FOR THIS PRODUCT:
{variants_list}

IMPORTANT: When user mentions a variant (e.g., "3 bunches", "1kg", "the smallest one"), use the CORRECT Variant ID from the list above, NOT the number from their description. For example, if user says "3 bunches" and the variant "3 bunches" has Variant ID 54, use variant_id=54, NOT variant_id=3.
"""
            base_prompt += product_info
        
        return base_prompt
    
    def get_function_declarations(self) -> List[Dict]:
        """Get function declarations for Gemini Function Calling"""
        return [
            {
                'name': 'search_products',
                'description': 'Search for products by name or keywords. ALWAYS use this function when the user mentions any product name, food item, or asks about products (e.g., "carrot", "potatoes", "find apples", "show me vegetables"). Even single words like "carrot" or "apple" should trigger this search.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'query': {
                            'type': 'string',
                            'description': 'The search query for products. Extract the product name or keyword from user message. For example: if user says "carrot" or "find carrot" or "I want carrot", use "carrot" as the query. Remove stop words like "search", "find", "show me", "I want", "buy" but keep the actual product name.'
                        }
                    },
                    'required': ['query']
                }
            },
            {
                'name': 'get_cart',
                'description': 'Retrieve the current shopping cart contents for the user. Use this when the user asks to see their cart, wants to know what\'s in their cart, or says "my cart".',
                'parameters': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                }
            },
            {
                'name': 'add_to_cart',
                'description': 'Add a specified quantity of a product to the user\'s shopping cart. Use this when the user wants to add a product, says "add it", "I want [product]", or confirms buying a product. If product has variants and user specified one (e.g., "1kg", "smallest"), include variant_id. If user didn\'t specify variant, call add_to_cart anyway - system will auto-select first variant.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'product_id': {
                            'type': 'integer',
                            'description': 'The unique identifier of the product to add to the cart. If user says "it", "this", or "that", use the most recently mentioned product ID. NEVER ask user for product ID - use product names or context.'
                        },
                        'quantity': {
                            'type': 'integer',
                            'description': 'The quantity of the product to add (default is 1).'
                        },
                        'variant_id': {
                            'type': 'integer',
                            'description': 'OPTIONAL: The variant ID if the product has variants and user specified one. If user describes variant (e.g., "1kg", "smallest", "cheapest", "first one"), try to match and include variant_id. If not specified, system will auto-select first variant.'
                        }
                    },
                    'required': ['product_id']
                }
            },
            {
                'name': 'get_product_variants',
                'description': 'Get available variants (sizes, weights, etc.) for a product that has variants. Use this when a product has variants and the user wants to see options or when add_to_cart fails because product has variants.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'product_id': {
                            'type': 'integer',
                            'description': 'The unique identifier of the product to get variants for.'
                        }
                    },
                    'required': ['product_id']
                }
            },
            {
                'name': 'create_order',
                'description': 'Create a new order from the items currently in the user\'s shopping cart. Use this when the user explicitly asks to checkout, place an order, or complete purchase.',
                'parameters': {
                    'type': 'object',
                    'properties': {},
                    'required': []
                }
            },
            {
                'name': 'get_orders',
                'description': 'Retrieve a list of the user\'s past orders. Use this when the user asks to see their order history, past orders, or "my orders".',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'limit': {
                            'type': 'integer',
                            'description': 'The maximum number of recent orders to retrieve (default is 5).'
                        }
                    },
                    'required': []
                }
            },
            {
                'name': 'get_product_details',
                'description': 'Retrieve detailed information about a specific product. Use this when the user asks for details about a product or wants to know more about a specific product.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'product_id': {
                            'type': 'integer',
                            'description': 'The unique identifier of the product to get details for.'
                        }
                    },
                    'required': ['product_id']
                }
            }
        ]
    
    def build_conversation_history(self, messages: List[Dict]) -> List[Dict]:
        """Xây dựng lịch sử hội thoại cho Gemini"""
        history = []
        
        for msg in messages[-10:]:  # Chỉ lấy 10 tin nhắn gần nhất
            role = 'user' if not msg.get('is_bot') else 'model'
            content = msg.get('content', '')
            
            if role == 'user':
                history.append({
                    'role': 'user',
                    'parts': [content]
                })
            else:
                history.append({
                    'role': 'model',
                    'parts': [content]
                })
        
        return history
    
    def process_message(
        self,
        user_message: str,
        conversation_history: List[Dict],
        user_context: Optional[Dict] = None,
        mentioned_product: Optional[Dict] = None,
        function_executor: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Process message with Gemini AI using native function calling
        
        Args:
            user_message: Message from the user
            conversation_history: Conversation history
            user_context: User context
            mentioned_product: Most recently mentioned product
            function_executor: Function to execute function calls (should be async-aware)
        
        Returns:
            Dict with keys: 'response', 'function_call', 'function_result'
        """
        # Fallback mode if Gemini is not available
        if not self.model:
            return self._fallback_response(user_message)
        
        try:
            # Build system prompt
            system_prompt = self.build_system_prompt(user_context, mentioned_product)
            
            # Build conversation history
            history = self.build_conversation_history(conversation_history)
            
            # Prepare tools (function declarations) for Gemini
            function_declarations = self.get_function_declarations()
            tools = [{
                'function_declarations': function_declarations
            }]
            
            logger.info(f"🔧 Prepared {len(function_declarations)} function declarations for Gemini")
            logger.info(f"🔧 Functions available: {[f['name'] for f in function_declarations]}")
            
            # Build the full prompt with system message
            # Combine system prompt with user message
            full_prompt = f"{system_prompt}\n\nUser: {user_message}"
            
            # Prepare messages for chat (combine history with current message)
            all_messages = []
            for msg in history:
                all_messages.append(msg)
            all_messages.append({'role': 'user', 'parts': [full_prompt]})
            
            logger.info(f"📤 Calling Gemini API with {len(all_messages)} messages and {len(tools)} tool(s)")
            
            # Call Gemini API with function calling support
            response = self.model.generate_content(
                all_messages,
                tools=tools,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    top_p=0.8,
                    top_k=40,
                    max_output_tokens=1024,
                )
            )
            
            logger.info(f"📥 Received response from Gemini")
            logger.info(f"📥 User message was: '{user_message}'")
            
            # Check if Gemini wants to call a function
            function_call = None
            function_result = None
            final_response_text = None
            
            # Check for function calls in the response
            logger.info(f"🔍 Checking response for function calls...")
            logger.info(f"🔍 Response candidates: {len(response.candidates) if response.candidates else 0}")
            
            # Log the full response structure for debugging
            if response.candidates:
                logger.debug(f"🔍 First candidate finish_reason: {response.candidates[0].finish_reason if hasattr(response.candidates[0], 'finish_reason') else 'N/A'}")
            
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                logger.info(f"🔍 Candidate content parts: {len(candidate.content.parts) if hasattr(candidate, 'content') and candidate.content.parts else 0}")
                
                if hasattr(candidate, 'content') and candidate.content.parts:
                    function_call_part = None
                    for i, part in enumerate(candidate.content.parts):
                        logger.info(f"🔍 Part {i}: type={type(part).__name__}, has function_call={hasattr(part, 'function_call')}")
                        # Check if this part is a function call
                        if hasattr(part, 'function_call'):
                            func_call = part.function_call
                            logger.info(f"🔍 function_call object: {func_call}, type: {type(func_call).__name__}")
                            # Check if it's a real function call object with name
                            if func_call and hasattr(func_call, 'name'):
                                func_name = func_call.name
                                logger.info(f"🔍 function_call.name: {func_name}")
                                if func_name:
                                    logger.info(f"✅ Found function call part: {func_name}")
                                    function_call_part = part
                                    break
                                else:
                                    logger.warning(f"⚠️ function_call.name is empty")
                            else:
                                logger.warning(f"⚠️ function_call is None or doesn't have name attribute")
                        
                        # Also check for text content in the part
                        if hasattr(part, 'text') and part.text:
                            logger.info(f"🔍 Part {i} also has text: {part.text[:100]}...")
                    
                    if function_call_part:
                        logger.info(f"✅ Function call part found, processing...")
                        # Gemini wants to call a function
                        func_call = function_call_part.function_call
                        try:
                            # Parse function arguments
                            # Gemini FunctionCall.args can be a protobuf Struct object
                            args_dict = {}
                            
                            if hasattr(func_call, 'args') and func_call.args:
                                args = func_call.args
                                
                                # Check if it's a protobuf Struct (has 'fields' attribute)
                                if hasattr(args, 'fields'):
                                    # Convert protobuf Struct to dict
                                    for key, value in args.fields.items():
                                        # Extract the actual value from protobuf Value object
                                        if hasattr(value, 'string_value'):
                                            args_dict[key] = value.string_value
                                        elif hasattr(value, 'number_value'):
                                            args_dict[key] = value.number_value
                                        elif hasattr(value, 'bool_value'):
                                            args_dict[key] = value.bool_value
                                        elif hasattr(value, 'list_value'):
                                            # Handle list values
                                            args_dict[key] = [v.string_value for v in value.list_value.values if hasattr(v, 'string_value')]
                                        else:
                                            # Fallback: try to convert to string
                                            args_dict[key] = str(value)
                                    logger.info(f"🔍 Parsed protobuf Struct args: {args_dict}")
                                elif isinstance(args, dict):
                                    args_dict = args
                                elif isinstance(args, str):
                                    try:
                                        args_dict = json.loads(args)
                                    except json.JSONDecodeError:
                                        logger.warning(f"⚠️ Could not parse args as JSON: {args}")
                                        args_dict = {}
                                else:
                                    # Try to convert to dict if possible
                                    try:
                                        if hasattr(args, 'items'):
                                            args_dict = dict(args)
                                        else:
                                            args_dict = {}
                                    except Exception as e:
                                        logger.warning(f"⚠️ Could not convert args to dict: {e}")
                                        args_dict = {}
                            
                            function_call = {
                                'name': func_call.name,
                                'arguments': args_dict
                            }
                            logger.info(f"🔧 Gemini requested function call: {function_call['name']} with args: {function_call.get('arguments', {})}")
                            
                            # Execute the function if executor is provided
                            if function_executor:
                                try:
                                    # Handle mentioned_product context for add_to_cart
                                    if function_call['name'] == 'add_to_cart' and mentioned_product:
                                        # If product_id is missing or user said "it"/"this"/"that", use mentioned product
                                        if 'product_id' not in function_call['arguments'] or function_call['arguments'].get('product_id') is None:
                                            function_call['arguments']['product_id'] = mentioned_product.get('product_id')
                                            logger.info(f"✅ Using mentioned product ID: {mentioned_product.get('product_id')}")
                                    
                                    # Execute function (function_executor should handle async if needed)
                                    logger.info(f"⚙️ Executing function: {function_call['name']}...")
                                    function_result = function_executor(function_call)
                                    logger.info(f"✅ Function executed! Success: {function_result.get('success', False)}, Result: {function_result}")
                                    
                                    # Verify function was actually executed
                                    if not function_result:
                                        logger.error(f"❌ Function {function_call['name']} returned None!")
                                        function_result = {'success': False, 'error': 'Function returned no result'}
                                    
                                    # Prepare function response for Gemini
                                    # Use a simple approach: generate natural response from function result
                                    # Gemini's function calling will be handled by the model itself
                                    try:
                                        # Generate a natural language response based on function result
                                        # This ensures we always return natural text, not JSON
                                        final_response_text = self._generate_response_from_function_result(
                                            function_call['name'],
                                            function_result
                                        )
                                        
                                        # Only refine response if function was successful
                                        # Always verify function_result before using refined response
                                        if function_result.get('success'):
                                            logger.info(f"✅ Function {function_call['name']} succeeded, generating response")
                                            # Try to get Gemini to generate a more natural response
                                            try:
                                                refinement_prompt = f"""
Based on this function result, respond naturally to the user:

Function: {function_call['name']}
Result: {json.dumps(function_result, ensure_ascii=False)}

Respond in a friendly, natural way in English. Don't include JSON or technical details.
Make sure your response confirms the action was completed successfully.
"""
                                                refined_response = self.model.generate_content(
                                                    refinement_prompt,
                                                    generation_config=genai.types.GenerationConfig(
                                                        temperature=0.7,
                                                        max_output_tokens=256,
                                                    )
                                                )
                                                if refined_response and refined_response.text:
                                                    # Verify the refined response makes sense
                                                    refined_text = refined_response.text.strip()
                                                    if refined_text and len(refined_text) > 10:  # Ensure it's a real response
                                                        final_response_text = refined_text
                                                        logger.info(f"✅ Using refined response from Gemini")
                                                    else:
                                                        logger.warning(f"⚠️ Refined response too short, using manual response")
                                            except Exception as refine_error:
                                                logger.debug(f"Could not refine response with Gemini: {refine_error}, using manual response")
                                        else:
                                            logger.warning(f"⚠️ Function {function_call['name']} failed: {function_result.get('error', 'Unknown error')}")
                                    except Exception as e:
                                        logger.error(f"Error generating response from function result: {str(e)}", exc_info=True)
                                        final_response_text = self._generate_response_from_function_result(
                                            function_call['name'],
                                            function_result
                                        )
                                        
                                except Exception as e:
                                    logger.error(f"Error executing function: {str(e)}", exc_info=True)
                                    function_result = {'success': False, 'error': str(e)}
                                    final_response_text = f"I encountered an error while processing your request: {str(e)}. Please try again."
                            else:
                                logger.warning("Function executor not provided, cannot execute function call")
                                function_result = {'success': False, 'error': 'Function executor not available'}
                                final_response_text = "I understand you want to perform an action, but I'm unable to execute it right now. Please try again."
                                
                        except Exception as e:
                            logger.error(f"Error parsing function call: {str(e)}", exc_info=True)
                            function_result = {'success': False, 'error': str(e)}
                            final_response_text = "I encountered an error processing your request. Please try again."
            
            # If no function call was made, use Gemini's natural response
            if not function_call:
                if response.text:
                    final_response_text = response.text
                    logger.warning(f"⚠️ No function call detected! Gemini responded with text only: {final_response_text[:200]}...")
                    logger.warning(f"⚠️ This means Gemini didn't call any function - it just generated a text response")
                else:
                    logger.warning(f"⚠️ No function call and no text response from Gemini")
            
            # Ensure we have a response
            if not final_response_text:
                final_response_text = "I received your message. How can I help you?"
            
            # Log final result
            if function_call:
                logger.info(f"📊 Final result - Function: {function_call['name']}, Success: {function_result.get('success') if function_result else 'N/A'}, Response length: {len(final_response_text) if final_response_text else 0}")
            else:
                logger.info(f"📊 Final result - No function call, Response length: {len(final_response_text) if final_response_text else 0}")
            
            return {
                'response': final_response_text,
                'function_call': function_call,
                'function_result': function_result
            }
            
        except Exception as e:
            logger.error(f"Error processing message with Gemini: {str(e)}", exc_info=True)
            return self._fallback_response(user_message)
    
    def _generate_response_from_function_result(self, function_name: str, function_result: Dict) -> str:
        """Generate a natural language response from function result"""
        # Special handling for add_to_cart with variants - show variants even if failed
        if function_name == 'add_to_cart' and not function_result.get('success') and function_result.get('has_variants'):
            variants = function_result.get('variants', [])
            if variants:
                variant_list = "\n".join([
                    f"• {v['variant_name']} - ${v['price']:,.2f}" + 
                    (f" (Stock: {v['stock']})" if v.get('is_in_stock') else " - Out of stock")
                    for v in variants
                ])
                product_id = function_result.get('product_id')
                return f"📦 This product has different options available:\n\n{variant_list}\n\nWhich option would you like? You can say:\n• 'I want the [variant name]' (e.g., 'I want the 1 bunch')\n• Or just describe what you need (e.g., 'the smallest one', 'the cheapest option')"
        
        if not function_result.get('success'):
            error_msg = function_result.get('error', 'Unknown error')
            return f"I'm sorry, I couldn't complete that action. {error_msg}"
        
        if function_name == 'search_products':
            products = function_result.get('products', [])
            count = function_result.get('count', 0)
            if count > 0:
                product_list = "\n".join([f"• {p['name']} - ${p['price']:,.2f}" for p in products[:5]])
                return f"Great! I found {count} product(s):\n\n{product_list}\n\nWould you like to add any of these to your cart? You can say:\n• 'add [product name]' (e.g., 'add bananas')\n• 'add it' for the first one\n• 'I want [product name]'"
            else:
                return "I couldn't find any products matching your search. Could you try different keywords?"
        
        elif function_name == 'add_to_cart':
            product_name = function_result.get('product_name', 'product')
            variant_name = function_result.get('variant_name')
            quantity = function_result.get('quantity', 1)
            auto_selected = function_result.get('auto_selected_variant', False)
            
            if variant_name:
                product_display = f"{product_name} ({variant_name})"
                if auto_selected:
                    return f"✅ Perfect! I've added {quantity} x {product_display} to your cart. I selected the '{variant_name}' option for you. Would you like to add more items or proceed to checkout? You can say 'checkout' when you're ready."
                else:
                    return f"✅ Perfect! I've added {quantity} x {product_display} to your cart. Would you like to add more items or proceed to checkout? You can say 'checkout' when you're ready."
            else:
                return f"✅ Perfect! I've added {quantity} x {product_name} to your cart. Would you like to add more items or proceed to checkout? You can say 'checkout' when you're ready."
        
        elif function_name == 'get_cart':
            items = function_result.get('items', [])
            if items:
                total = function_result.get('total', 0)
                item_list = "\n".join([f"- {item['name']} x{item['quantity']} - ${item['subtotal']:,.2f}" for item in items])
                return f"Here's what's in your cart:\n\n{item_list}\n\nTotal: ${total:,.2f}\n\nReady to checkout? Just say 'checkout' or 'place order'."
            else:
                return "Your cart is empty. Would you like to search for some products?"
        
        elif function_name == 'create_order':
            order_id = function_result.get('order_id', 'N/A')
            total = function_result.get('total_amount', 0)
            return f"🎉 Order placed successfully! Your order ID is {order_id} and the total is ${total:,.2f}. Thank you for your purchase!"
        
        elif function_name == 'get_orders':
            orders = function_result.get('orders', [])
            count = function_result.get('count', 0)
            if count > 0:
                order_list = "\n".join([f"- Order {o['order_id']}: ${o['total_amount']:,.2f} ({o['status']})" for o in orders[:5]])
                return f"Here are your recent orders:\n\n{order_list}"
            else:
                return "You don't have any orders yet. Would you like to start shopping?"
        
        elif function_name == 'get_product_details':
            product = function_result.get('product', {})
            if product:
                return f"Here are the details for {product.get('name', 'this product')}:\n\nPrice: ${product.get('price', 0):,.2f}\nStore: {product.get('store_name', 'N/A')}\n\nWould you like to add it to your cart?"
            else:
                return "I couldn't find details for that product."
        
        elif function_name == 'get_product_variants':
            variants = function_result.get('variants', [])
            product_name = function_result.get('product_name', 'This product')
            product_id = function_result.get('product_id')
            count = function_result.get('count', 0)
            
            if count > 0:
                variant_list = "\n".join([
                    f"- {v['variant_name']} (Variant ID: {v['variant_id']}) - ${v['price']:,.2f}" + 
                    (f" - Stock: {v['stock']}" if v.get('is_in_stock') else " - Out of stock")
                    for v in variants
                ])
                return f"{product_name} has {count} option(s) available:\n\n{variant_list}\n\nWhich variant would you like? You can say 'add variant [ID]' or describe the variant you want (e.g., 'I want the 1kg one')."
            else:
                return f"I couldn't find any variants for {product_name}."
        
        return "Action completed successfully!"
    
    def _fallback_response(self, user_message: str) -> Dict[str, Any]:
        """Fallback response when Gemini is not available"""
        function_call = self._detect_function_call(user_message, "")
        
        return {
            'response': 'Hello! I can help you search for products, view your cart, and place orders. Please try commands like "search products", "cart", or "place order".',
            'function_call': function_call,
            'function_result': None
        }
    
    def _parse_function_call_from_response(self, ai_response: str, user_message: str, conversation_history: List[Dict]) -> Optional[Dict]:
        """
        Parse function call from AI response intelligently based on context.
        Let AI decide when to call functions based on full conversation context.
        """
        import re
        
        # First, try to parse JSON format if AI used structured output
        try:
            # Look for JSON in the response - try multiple patterns
            json_patterns = [
                r'\{[^{}]*"function_call"[^{}]*\}',
                r'\{.*?"function_call".*?\}',
                r'function_call.*?\{.*?\}',
            ]
            for pattern in json_patterns:
                json_match = re.search(pattern, ai_response, re.DOTALL | re.IGNORECASE)
                if json_match:
                    try:
                        parsed = json.loads(json_match.group())
                        if 'function_call' in parsed and isinstance(parsed['function_call'], dict):
                            return parsed['function_call']
                    except:
                        continue
        except Exception as e:
            logger.debug(f"Error parsing JSON from AI response: {e}")
        
        # If no JSON found, analyze contextually
        # Don't treat simple confirmations as search queries
        simple_responses = ['yes', 'no', 'ok', 'okay', 'sure', 'yep', 'nope', 'alright', 'yeah', 'nah']
        user_lower = user_message.lower().strip()
        
        if user_lower in simple_responses:
            # User is responding to a question - check conversation history for context
            if conversation_history:
                # Look at recent bot messages to understand what user is confirming
                recent_bot_messages = [msg for msg in conversation_history[-5:] if msg.get('is_bot')]
                if recent_bot_messages:
                    last_bot_msg = recent_bot_messages[-1].get('content', '').lower()
                    
                    # If bot asked about buying/adding a product, user likely wants to proceed with that action
                    if any(phrase in last_bot_msg for phrase in ['buy', 'add to cart', 'add it', 'proceed']):
                        # Check if there's a mentioned product to add
                        # Return add_to_cart function call if product is known
                        return None  # Let the system handle it based on mentioned_product
                    
                    # If bot asked about searching, don't search for "yes"
                    if 'search' in last_bot_msg or 'find' in last_bot_msg:
                        return None  # Don't search for "yes"
            
            # For simple responses, don't call any function - let AI respond naturally
            return None
        
        # For other messages, use minimal keyword detection only for very clear intents
        # Most function calls should come from AI's understanding of context
        return self._detect_function_call(user_message, ai_response)
    
    def _detect_function_call(self, user_message: str, ai_response: str) -> Optional[Dict]:
        """
        Detect function call từ user message và AI response
        Sử dụng pattern matching và keyword detection
        """
        message_lower = user_message.lower()
        
        # Only use keyword detection as a last resort fallback
        # Most function calls should be determined by AI based on context
        
        # Exclude simple responses and help requests from search
        simple_responses = ['yes', 'no', 'ok', 'okay', 'sure', 'yep', 'nope', 'alright', 'thanks', 'thank you']
        help_phrases = ['help me', 'help to', 'how to', 'how do i', 'guide me', 'assist me']
        
        if message_lower.strip() in simple_responses or any(phrase in message_lower for phrase in help_phrases):
            return None  # Don't treat these as search queries
        
        # Only detect clear search intents
        search_keywords = ['search', 'find', 'look for', 'show me products', 'what products']
        if any(keyword in message_lower for keyword in search_keywords):
            query = self._extract_search_query(user_message)
            if query and len(query.strip()) > 0:
                return {
                    'name': 'search_products',
                    'arguments': {'query': query}
                }
        
        # View cart
        if any(keyword in message_lower for keyword in ['cart', 'shopping cart', 'my cart', 'view cart', 'show cart']):
            return {
                'name': 'get_cart',
                'arguments': {}
            }
        
        # Add to cart
        if any(keyword in message_lower for keyword in ['add', 'add to cart', 'put in cart', 'buy product']):
            product_id = self._extract_product_id(user_message)
            quantity = self._extract_quantity(user_message)
            if product_id:
                return {
                    'name': 'add_to_cart',
                    'arguments': {
                        'product_id': product_id,
                        'quantity': quantity or 1
                    }
                }
        
        # View orders (check this before create_order to avoid conflicts)
        if any(keyword in message_lower for keyword in ['orders', 'my orders', 'order history', 'past orders', 'view orders']):
            return {
                'name': 'get_orders',
                'arguments': {'limit': 5}
            }
        
        # Place order
        if any(keyword in message_lower for keyword in ['checkout', 'place order', 'purchase']):
            return {
                'name': 'create_order',
                'arguments': {}
            }
        
        return None
    
    def _extract_search_query(self, message: str) -> Optional[str]:
        """Extract search query from message"""
        import re
        # Remove common stop words and search keywords
        stop_words = {'search', 'find', 'look', 'for', 'product', 'products', 'show', 'me', 
                     'i', 'want', 'to', 'buy', 'need', 'get', 'see', 'a', 'an', 'the', 
                     'some', 'any', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                     'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'can', 'could',
                     'help', 'it', 'this', 'that', 'them', 'these', 'those'}  # Added pronouns and help
        
        # Extract words, keeping only meaningful ones
        words = re.findall(r'\b\w+\b', message.lower())
        query_words = [w for w in words if w not in stop_words and len(w) > 1]
        
        # If we have query words, return them; otherwise try to extract the last meaningful word
        if query_words:
            query = ' '.join(query_words)
            # If query is too long (more than 5 words), take the last few words
            if len(query_words) > 5:
                query = ' '.join(query_words[-5:])
            return query.strip() if query.strip() else None
        
        # Fallback: return None if no meaningful words found (likely a help request or pronoun)
        return None
    
    def _extract_product_id(self, message: str) -> Optional[int]:
        """Extract product ID từ message"""
        numbers = re.findall(r'\d+', message)
        return int(numbers[0]) if numbers else None
    
    def _extract_quantity(self, message: str) -> Optional[int]:
        """Extract quantity from message"""
        # Find quantity (e.g., "2 items", "3 products")
        patterns = [
            r'(\d+)\s*(items?|products?|pieces?)',
            r'(buy|add|get)\s*(\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, message.lower())
            if match:
                return int(match.group(1) if match.group(1).isdigit() else match.group(2))
        return None


# Singleton instance
_gemini_service = None

def get_gemini_service() -> GeminiAIService:
    """Get singleton instance of GeminiAIService"""
    global _gemini_service
    if _gemini_service is None:
        try:
            _gemini_service = GeminiAIService()
        except Exception as e:
            logger.error(f"Error creating Gemini service: {str(e)}")
            _gemini_service = GeminiAIService()  # Will use fallback mode
    return _gemini_service

