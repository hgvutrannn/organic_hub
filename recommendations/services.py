import logging
from typing import List, Optional
from django.db.models import Q, Count, Sum, Avg
from django.core.cache import cache
from django.conf import settings
from core.models import Product, OrderItem, Review, Category

logger = logging.getLogger(__name__)


class RecommendationService:
    """Service for generating personalized product recommendations"""
    
    CACHE_TTL_USER = 3600  # 1 hour
    CACHE_TTL_SESSION = 1800  # 30 minutes
    CACHE_TTL_BESTSELLING = 7200  # 2 hours
    CACHE_TTL_PRODUCT = 3600  # 1 hour

    @staticmethod
    def get_best_selling_products(limit: int = 12) -> List[Product]:
        """
        Fallback method: Get best selling products by total quantity sold.
        This method should never fail - it's the fallback for all other methods.
        """
        try:
            cache_key = f'rec:bestselling:{limit}'
            cached = cache.get(cache_key)
            if cached:
                product_ids = cached
                products = Product.objects.filter(
                    product_id__in=product_ids,
                    is_active=True
                )
                # Preserve order
                product_dict = {p.product_id: p for p in products}
                return [product_dict[pid] for pid in product_ids if pid in product_dict]
            
            # Query best selling products
            best_selling = OrderItem.objects.values('product').annotate(
                total_sold=Sum('quantity')
            ).order_by('-total_sold')[:limit]
            
            product_ids = [item['product'] for item in best_selling]
            
            # Get products
            products = Product.objects.filter(
                product_id__in=product_ids,
                is_active=True
            )
            
            # If we don't have enough products, fill with most viewed
            if products.count() < limit:
                remaining = limit - products.count()
                viewed_products = Product.objects.filter(
                    is_active=True
                ).exclude(
                    product_id__in=product_ids
                ).order_by('-view_count')[:remaining]
                products = list(products) + list(viewed_products)
            
            # Cache the result
            cache.set(cache_key, product_ids, RecommendationService.CACHE_TTL_BESTSELLING)
            
            return list(products)
        except Exception as e:
            logger.error(f"Error in get_best_selling_products: {e}", exc_info=True)
            # Ultimate fallback: just return active products ordered by view count
            try:
                return list(Product.objects.filter(is_active=True).order_by('-view_count')[:limit])
            except Exception as e2:
                logger.error(f"Ultimate fallback also failed: {e2}", exc_info=True)
                return []

    @staticmethod
    def get_personalized_recommendations(user, limit: int = 12) -> List[Product]:
        """
        Get personalized recommendations for authenticated user using hybrid approach.
        Falls back to best selling products on error.
        """
        if not user or not user.is_authenticated:
            return RecommendationService.get_best_selling_products(limit)
        
        try:
            cache_key = f'rec:user:{user.user_id}:{limit}'
            cached = cache.get(cache_key)
            if cached:
                product_ids = cached
                products = Product.objects.filter(
                    product_id__in=product_ids,
                    is_active=True
                )
                product_dict = {p.product_id: p for p in products}
                return [product_dict[pid] for pid in product_ids if pid in product_dict]
            
            """Get user preferences from purchase and view history 
            Output: preferences = {
            'categories': set(),
            'price_range': None,
            'stores': set(),
            }
            """
            user_preferences = RecommendationService._get_user_preferences(user)
            
            # Get content-based recommendations (60% weight) return a list of products that match user preferences
            content_based = RecommendationService._get_content_based_for_user(
                user, user_preferences, limit=int(limit * 0.6)
            )
            
            # Get collaborative recommendations (40% weight) from similar users. return a list of products
            collaborative = RecommendationService.get_collaborative_recommendations(
                user, limit=int(limit * 0.4)
            )
            
            # Combine and score
            all_products = list(set(content_based + collaborative))
            scored_products = RecommendationService._score_products(
                all_products, user, user_preferences
            )
            
            # Sort by score and take top N
            scored_products.sort(key=lambda x: x[1], reverse=True)
            recommended = [p[0] for p in scored_products[:limit]]
            
            # Priority 1: Exclude already purchased products
            purchased_ids = OrderItem.objects.filter(
                order__user=user,
                order__status='delivered'
            ).values_list('product', flat=True).distinct()
            
            recommended = [p for p in recommended if p.product_id not in purchased_ids]
            
            # If we removed too many, fill with more from scored_products
            if len(recommended) < limit:
                remaining = limit - len(recommended)
                purchased_set = set(purchased_ids)
                recommended_set = {p.product_id for p in recommended}
                
                for p, score in scored_products[len(recommended):]:
                    if p.product_id not in purchased_set and p.product_id not in recommended_set:
                        recommended.append(p)
                        recommended_set.add(p.product_id)
                        if len(recommended) >= limit:
                            break
            
            # Cache result
            product_ids = [p.product_id for p in recommended[:limit]]
            cache.set(cache_key, product_ids, RecommendationService.CACHE_TTL_USER)
            
            return recommended[:limit]
        except Exception as e:
            logger.error(f"Error in get_personalized_recommendations for user {user.user_id}: {e}", exc_info=True)
            return RecommendationService.get_best_selling_products(limit)

    @staticmethod
    def get_session_recommendations(session_key: str, limit: int = 12) -> List[Product]:
        """
        Get recommendations for anonymous users based on session browsing history.
        Falls back to best selling products on error.
        """
        if not session_key:
            return RecommendationService.get_best_selling_products(limit)
        
        try:
            cache_key = f'rec:session:{session_key}:{limit}'
            cached = cache.get(cache_key)
            if cached:
                product_ids = cached
                products = Product.objects.filter(
                    product_id__in=product_ids,
                    is_active=True
                )
                product_dict = {p.product_id: p for p in products}
                return [product_dict[pid] for pid in product_ids if pid in product_dict]
            
            from recommendations.models import UserProductView
            
            # Get viewed products in this session
            viewed_products = UserProductView.objects.filter(
                session_key=session_key
            ).select_related('product').order_by('-viewed_at')[:10]
            
            if not viewed_products.exists():
                return RecommendationService.get_best_selling_products(limit)
            
            # Get categories from viewed products
            viewed_categories = set()
            for view in viewed_products:
                if view.product.category:
                    viewed_categories.add(view.product.category.category_id)
            
            # Recommend products from same categories
            recommended = Product.objects.filter(
                is_active=True,
                category_id__in=viewed_categories
            ).exclude(
                product_id__in=[v.product.product_id for v in viewed_products]
            ).order_by('-view_count')[:limit]
            
            # If not enough, fill with best selling
            if recommended.count() < limit:
                remaining = limit - recommended.count()
                best_selling = RecommendationService.get_best_selling_products(remaining)
                recommended = list(recommended) + best_selling
            
            # Priority 2: Remove duplicates
            seen_ids = set()
            unique_recommended = []
            viewed_product_ids = {v.product.product_id for v in viewed_products}
            
            for p in recommended:
                if p.product_id not in seen_ids and p.product_id not in viewed_product_ids:
                    seen_ids.add(p.product_id)
                    unique_recommended.append(p)
                if len(unique_recommended) >= limit:
                    break
            
            # Cache result
            product_ids = [p.product_id for p in unique_recommended[:limit]]
            cache.set(cache_key, product_ids, RecommendationService.CACHE_TTL_SESSION)
            
            return unique_recommended[:limit]
        except Exception as e:
            logger.error(f"Error in get_session_recommendations for session {session_key}: {e}", exc_info=True)
            return RecommendationService.get_best_selling_products(limit)

    @staticmethod
    def get_similar_products(product: Product, limit: int = 8) -> List[Product]:
        """
        Get products similar to the given product based on category and description.
        Falls back to best selling products on error.
        """
        if not product:
            return RecommendationService.get_best_selling_products(limit)
        
        try:
            cache_key = f'rec:product:{product.product_id}:similar:{limit}'
            cached = cache.get(cache_key)
            if cached:
                product_ids = cached
                products = Product.objects.filter(
                    product_id__in=product_ids,
                    is_active=True
                ).exclude(product_id=product.product_id)
                product_dict = {p.product_id: p for p in products}
                return [product_dict[pid] for pid in product_ids if pid in product_dict]
            
            similar = []
            
            # Same category products
            if product.category:
                category_products = Product.objects.filter(
                    category=product.category,
                    is_active=True
                ).exclude(product_id=product.product_id).order_by('-view_count')[:limit]
                similar.extend(category_products)
            
            # Same store products
            store_products = Product.objects.filter(
                store=product.store,
                is_active=True
            ).exclude(product_id=product.product_id).order_by('-view_count')[:limit]
            similar.extend(store_products)
            
            # Remove duplicates and limit
            seen = set()
            unique_similar = []
            for p in similar:
                if p.product_id not in seen:
                    seen.add(p.product_id)
                    unique_similar.append(p)
                if len(unique_similar) >= limit:
                    break
            
            # If not enough, fill with best selling
            if len(unique_similar) < limit:
                remaining = limit - len(unique_similar)
                best_selling = RecommendationService.get_best_selling_products(remaining)
                for p in best_selling:
                    if p.product_id not in seen:
                        unique_similar.append(p)
                    if len(unique_similar) >= limit:
                        break
            
            # Ensure product itself is excluded
            unique_similar = [p for p in unique_similar if p.product_id != product.product_id]
            
            # Cache result
            product_ids = [p.product_id for p in unique_similar[:limit]]
            cache.set(cache_key, product_ids, RecommendationService.CACHE_TTL_PRODUCT)
            
            return unique_similar[:limit]
        except Exception as e:
            logger.error(f"Error in get_similar_products for product {product.product_id}: {e}", exc_info=True)
            return RecommendationService.get_best_selling_products(limit)

    @staticmethod
    def get_frequently_bought_together(product: Product, limit: int = 4) -> List[Product]:
        """
        Get products frequently bought together with the given product.
        Falls back to best selling products on error.
        """
        if not product:
            return RecommendationService.get_best_selling_products(limit)
        
        try:
            cache_key = f'rec:product:{product.product_id}:together:{limit}'
            cached = cache.get(cache_key)
            if cached:
                product_ids = cached
                products = Product.objects.filter(
                    product_id__in=product_ids,
                    is_active=True
                ).exclude(product_id=product.product_id)
                product_dict = {p.product_id: p for p in products}
                return [product_dict[pid] for pid in product_ids if pid in product_dict]
            
            # Get orders that contain this product
            orders_with_product = OrderItem.objects.filter(
                product=product
            ).values_list('order', flat=True).distinct()
            
            if not orders_with_product:
                return RecommendationService.get_best_selling_products(limit)
            
            # Get other products in those orders
            together_products = OrderItem.objects.filter(
                order__in=orders_with_product
            ).exclude(
                product=product
            ).values('product').annotate(
                count=Count('product')
            ).order_by('-count')[:limit]
            
            product_ids = [item['product'] for item in together_products]
            
            if not product_ids:
                return RecommendationService.get_best_selling_products(limit)
            
            products = Product.objects.filter(
                product_id__in=product_ids,
                is_active=True
            )
            
            # Preserve order by count
            product_dict = {p.product_id: p for p in products}
            result = [product_dict[pid] for pid in product_ids if pid in product_dict]
            
            # Fill if needed
            if len(result) < limit:
                remaining = limit - len(result)
                best_selling = RecommendationService.get_best_selling_products(remaining)
                seen_ids = set(product_ids)
                for p in best_selling:
                    if p.product_id not in seen_ids:
                        result.append(p)
                    if len(result) >= limit:
                        break
            
            # Ensure product itself is excluded
            result = [p for p in result if p.product_id != product.product_id]
            
            # Cache result
            product_ids = [p.product_id for p in result[:limit]]
            cache.set(cache_key, product_ids, RecommendationService.CACHE_TTL_PRODUCT)
            
            return result[:limit]
        except Exception as e:
            logger.error(f"Error in get_frequently_bought_together for product {product.product_id}: {e}", exc_info=True)
            return RecommendationService.get_best_selling_products(limit)

    @staticmethod
    def get_content_based_recommendations(product: Product, user=None, limit: int = 8) -> List[Product]:
        """
        Get content-based recommendations for a product.
        Falls back to best selling products on error.
        """
        return RecommendationService.get_similar_products(product, limit)

    @staticmethod
    def get_collaborative_recommendations(user, limit: int = 8) -> List[Product]:
        """
        Get collaborative filtering recommendations based on similar users.
        Falls back to best selling products on error.
        """
        if not user or not user.is_authenticated:
            return RecommendationService.get_best_selling_products(limit)
        
        try:
            # Get users with similar purchase history
            user_orders = OrderItem.objects.filter(order__user=user).values_list('product', flat=True).distinct()
            
            if not user_orders:
                return RecommendationService.get_best_selling_products(limit)
            
            # Find similar users (users who bought same products)
            similar_users = OrderItem.objects.filter(
                product__in=user_orders
            ).exclude(
                order__user=user
            ).values('order__user').annotate(
                similarity=Count('product')
            ).order_by('-similarity')[:10]
            
            if not similar_users:
                return RecommendationService.get_best_selling_products(limit)
            
            similar_user_ids = [item['order__user'] for item in similar_users]
            
            # Get products bought by similar users
            recommended_products = OrderItem.objects.filter(
                order__user__in=similar_user_ids
            ).exclude(
                product__in=user_orders
            ).values('product').annotate(
                score=Count('product')
            ).order_by('-score')[:limit]
            
            product_ids = [item['product'] for item in recommended_products]
            
            if not product_ids:
                return RecommendationService.get_best_selling_products(limit)
            
            products = Product.objects.filter(
                product_id__in=product_ids,
                is_active=True
            )
            
            product_dict = {p.product_id: p for p in products}
            result = [product_dict[pid] for pid in product_ids if pid in product_dict]
            
            # Fill if needed
            if len(result) < limit:
                remaining = limit - len(result)
                best_selling = RecommendationService.get_best_selling_products(remaining)
                seen_ids = set(product_ids)
                for p in best_selling:
                    if p.product_id not in seen_ids:
                        result.append(p)
                    if len(result) >= limit:
                        break
            
            return result[:limit]
        except Exception as e:
            logger.error(f"Error in get_collaborative_recommendations for user {user.user_id}: {e}", exc_info=True)
            return RecommendationService.get_best_selling_products(limit)

    # Helper methods
    @staticmethod
    def _get_user_preferences(user):
        """Get user preferences from purchase and view history"""
        preferences = {
            'categories': set(),
            'price_range': None,
            'stores': set(),
        }
        
        try:
            # Get purchased products
            purchased_products = Product.objects.filter(
                order_items__order__user=user,
                order_items__order__status='delivered'
            ).distinct()
            
            for product in purchased_products:
                if product.category:
                    preferences['categories'].add(product.category.category_id)
                preferences['stores'].add(product.store.store_id)
            
            # Get viewed products
            from recommendations.models import UserProductView
            viewed_products = UserProductView.objects.filter(
                user=user
            ).select_related('product').order_by('-viewed_at')[:20]
            
            for view in viewed_products:
                if view.product.category:
                    preferences['categories'].add(view.product.category.category_id)
            
            # Calculate price range from purchases
            if purchased_products.exists():
                prices = [float(p.min_price) for p in purchased_products if p.min_price]
                if prices:
                    preferences['price_range'] = {
                        'min': min(prices),
                        'max': max(prices),
                        'avg': sum(prices) / len(prices)
                    }
        except Exception as e:
            logger.error(f"Error getting user preferences: {e}", exc_info=True)
        
        return preferences

    @staticmethod
    def _get_content_based_for_user(user, preferences, limit: int):
        """Get content-based recommendations for user"""
        try:
            products = Product.objects.filter(is_active=True)
            
            # Filter by preferred categories
            if preferences['categories']:
                products = products.filter(category_id__in=preferences['categories'])
            
            # Filter by price range if available
            # Priority 3: Make price filter more lenient (0.5 - 1.5 instead of 0.7 - 1.3)
            if preferences['price_range']:
                price_range = preferences['price_range']
                products = products.filter(
                    price__gte=price_range['min'] * 0.5,
                    price__lte=price_range['max'] * 1.5
                )
            
            # Exclude already purchased
            purchased_ids = OrderItem.objects.filter(
                order__user=user
            ).values_list('product', flat=True).distinct()
            
            products = products.exclude(product_id__in=purchased_ids)
            
            return list(products.order_by('-view_count')[:limit])
        except Exception as e:
            logger.error(f"Error in _get_content_based_for_user: {e}", exc_info=True)
            return []

    @staticmethod
    def _score_products(products: List[Product], user, preferences):
        """Score products based on user preferences"""
        scored = []
        
        try:
            for product in products:
                score = 0.0
                
                # Category match (40%)
                if product.category and product.category.category_id in preferences['categories']:
                    score += 0.4
                
                # Price range match (20%)
                if preferences['price_range']:
                    price_range = preferences['price_range']
                    avg_price = price_range['avg']
                    if product.price:
                        price_diff = abs(float(product.price) - avg_price) / avg_price
                        if price_diff <= 0.3:  # Within 30%
                            score += 0.2 * (1 - price_diff / 0.3)
                
                # Store match (10%)
                if product.store.store_id in preferences['stores']:
                    score += 0.1
                
                # View count boost (10%)
                score += min(0.1, product.view_count / 10000.0)
                
                # Rating boost (20%)
                avg_rating = Review.objects.filter(
                    product=product,
                    is_approved=True
                ).aggregate(avg=Avg('rating'))['avg'] or 0
                
                if avg_rating > 0:
                    score += 0.2 * (avg_rating / 5.0)
                
                scored.append((product, score))
        except Exception as e:
            logger.error(f"Error in _score_products: {e}", exc_info=True)
            # Return products with default score
            scored = [(p, 0.5) for p in products]
        
        return scored

