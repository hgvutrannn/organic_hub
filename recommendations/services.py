import logging
from typing import List, Optional
from django.db.models import Q, Count, Sum, Avg
from django.core.cache import cache
from django.conf import settings
from core.models import Product, OrderItem, Review, Category

logger = logging.getLogger(__name__)


class RecommendationService:
    """Service for generating personalized product recommendations"""
    
    CACHE_TTL_BESTSELLING = 120  # 2 mintues - Only best selling products use cache

    @staticmethod
    def get_best_selling_products(limit: int = 6) -> List[Product]:
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
                    product_id__in=product_ids
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
                product_id__in=product_ids
            )
            # If we don't have enough products, fill with most viewed
            if products.count() < limit:

                remaining = limit - products.count()
                viewed_products = Product.objects.filter().exclude(
                    product_id__in=product_ids
                ).order_by('-view_count')[:remaining]
                products = list(products) + list(viewed_products)
            
            # Cache the result
            cache.set(cache_key, product_ids, RecommendationService.CACHE_TTL_BESTSELLING)
            
            return list(products)
        except Exception as e:
            logger.error(f"Error in get_best_selling_products: {e}", exc_info=True)
            # Ultimate fallback: just return products ordered by view count
            try:
                return list(Product.objects.all().order_by('-view_count')[:limit])
            except Exception as e2:
                logger.error(f"Ultimate fallback also failed: {e2}", exc_info=True)
                return []

    @staticmethod
    def get_personalized_recommendations(user, limit: int = 12) -> List[Product]:
        """
        Get personalized recommendations using hybrid approach:
        - Collaborative filtering products get base score 9.5/10
        - Content-based products get boosted by user preferences
        """
        if not user or not user.is_authenticated:
            return RecommendationService.get_best_selling_products(limit)
        
        try:
            user_preferences = RecommendationService._get_user_preferences(user)
            print(f"User preferences: {user_preferences}")

            # Get collaborative recommendations (NO fallback to best-selling)
            collaborative_products = RecommendationService._get_collaborative_recommendations_raw(
                user, limit=limit * 2  # Get more candidates
            )

            
            # Get content-based recommendations (already scored)
            content_based_products = RecommendationService._get_content_based_for_user(
                user, user_preferences, limit=limit * 2
            )
            print(f"Content-based products: {content_based_products}")
            
            # Combine all products (remove duplicates)
            all_products = {}
            
            # Add CF products with base score 9.5
            CF_BASE_SCORE = 0.95
            CB_BASE_SCORE = 0.05
            for product in collaborative_products:
                # Get content-based boost score from CB products if exists
                cb_score = 0.0
                for cb_item in content_based_products:
                    if cb_item['product'].product_id == product.product_id:
                        cb_score = cb_item['score']
                        break
                
                all_products[product.product_id] = {
                    'product': product,
                    'score': CF_BASE_SCORE + cb_score * CB_BASE_SCORE,
                }
                print(f"CF: {product.product_id} {CF_BASE_SCORE + cb_score * CB_BASE_SCORE}")
            
            # Add CB products (already have scores)
            for cb_item in content_based_products:
                product = cb_item['product']
                cb_score = cb_item['score']
                
                if product.product_id not in all_products:
                    all_products[product.product_id] = {
                        'product': product,
                        'score': cb_score * CB_BASE_SCORE,
                    }
                    print(f"CB: {product.product_id} {cb_score * CB_BASE_SCORE}")
            # Sort by score descending
            all_products = sorted(all_products.values(), key=lambda x: x['score'], reverse=True)
            # Exclude already purchased
            purchased_ids = OrderItem.objects.filter(
                order__user=user,
                order__status='delivered'
            ).values_list('product', flat=True).distinct()
            
            recommended = []
            for product_data in all_products:
                print(f"{product_data['score']}")
                product = product_data['product']
                if product.product_id not in purchased_ids:
                    recommended.append(product)
                    if len(recommended) >= limit:
                        break

            # Final fallback: if not enough, use best-selling
            if len(recommended) < limit:
                remaining = limit - len(recommended)
                best_selling = RecommendationService.get_best_selling_products(remaining)
                recommended_set = {p.product_id for p in recommended}
                for p in best_selling:
                    if p.product_id not in recommended_set:
                        recommended.append(p)
                        if len(recommended) >= limit:
                            break
            
            return recommended[:limit]
            
        except Exception as e:
            logger.error(f"Error in get_personalized_recommendations for user {user.user_id}: {e}", exc_info=True)
            return RecommendationService.get_best_selling_products(limit)

    @staticmethod
    def _get_collaborative_recommendations_raw(user, limit: int = 20) -> List[Product]:
        """
        Get collaborative filtering recommendations WITHOUT fallback to best-selling.
        Returns empty list if no similar users found.
        """
        if not user or not user.is_authenticated:
            return []
        
        try:
            # Get user's purchase history
            user_orders = OrderItem.objects.filter(
                order__user=user
            ).values_list('product', flat=True).distinct()
            
            if not user_orders:
                return []  # No fallback - return empty
            
            # Find similar users
            similar_users = OrderItem.objects.filter(
                product__in=user_orders
            ).exclude(
                order__user=user
            ).values('order__user').annotate(
                similarity=Count('product')
            ).order_by('-similarity')[:10]
            
            if not similar_users:
                return []  # No fallback - return empty
            
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
                return []  # No fallback - return empty
            
            products = Product.objects.filter(product_id__in=product_ids)
            product_dict = {p.product_id: p for p in products}
            result = [product_dict[pid] for pid in product_ids if pid in product_dict]
            
            return result
            
        except Exception as e:
            logger.error(f"Error in _get_collaborative_recommendations_raw: {e}", exc_info=True)
            return []  # Return empty on error, no fallback

    @staticmethod
    def get_similar_products(product: Product, limit: int = 8) -> List[Product]:
        """
        Get products similar to the given product based on category and description.
        Falls back to best selling products on error.
        """
        if not product:
            return RecommendationService.get_best_selling_products(limit)
        
        try:
            similar = []
            
            # Same category products
            if product.category:
                category_products = Product.objects.filter(
                    category=product.category
                ).exclude(product_id=product.product_id).order_by('-view_count')[:limit]
                similar.extend(category_products)
            
            # Same store products
            store_products = Product.objects.filter(
                store=product.store
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
                product_id__in=product_ids
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

    
    # Helper methods
    @staticmethod
    def _get_user_preferences(user):
        """Get user preferences from view history and purchases"""
        preferences = {
            'categories': set(),
            'stores': set(),
            'user_view_counts': {},  # product_id -> view_count
        }
        
        try:
            # Get categories and view counts from viewed products
            from recommendations.models import UserProductView
            viewed_products = UserProductView.objects.filter(
                user=user
            ).select_related('product', 'product__category').order_by('-viewed_at')
            
            for view in viewed_products:
                if view.product.category:
                    preferences['categories'].add(view.product.category.category_id)
                # Track view counts for scoring
                product_id = view.product.product_id
                if product_id not in preferences['user_view_counts']:
                    preferences['user_view_counts'][product_id] = 0
                preferences['user_view_counts'][product_id] += view.view_count
            
            # Get categories and stores from purchased products
            purchased_products = Product.objects.filter(
                order_items__order__user=user,
            ).distinct()
            
            for product in purchased_products:
                if product.category:
                    preferences['categories'].add(product.category.category_id)
                preferences['stores'].add(product.store.store_id)
            
        except Exception as e:
            logger.error(f"Error getting user preferences: {e}", exc_info=True)
        
        return preferences

    @staticmethod
    def _get_content_based_for_user(user, preferences, limit: int):
        """Get content-based recommendations for user with scores"""
        try:
            # Get categories from preferences (already includes both viewed and purchased)
            categories = preferences.get('categories', set())
            
            if not categories:
                return []
            
            # Filter products by categories
            products = Product.objects.filter(
                category_id__in=categories
            ).select_related('category', 'store')
            
            # Exclude already purchased
            purchased_ids = OrderItem.objects.filter(
                order__user=user
            ).values_list('product', flat=True).distinct()
            
            products = products.exclude(product_id__in=purchased_ids)
            
            # Get user view counts from preferences (already calculated)
            user_view_counts = preferences.get('user_view_counts', {})
            
            # Calculate max view count for normalization
            max_view_count = max(user_view_counts.values()) if user_view_counts else 1
            
            # Score products
            scored_products = []
            for product in products[:limit * 2]:  # Get more candidates for scoring
                score = 0.0
                
                # Category match: 50%
                if product.category and product.category.category_id in preferences['categories']:
                    score += 0.5
                
                # Store match: 20%
                if product.store.store_id in preferences['stores']:
                    score += 0.2
                
                # User view count: 30%
                user_view_count = user_view_counts.get(product.product_id, 0)
                if user_view_count > 0:
                    # Normalize view count (0-1 range)
                    normalized_view = min(1.0, user_view_count / max_view_count)
                    score += 0.3 * normalized_view
                
                scored_products.append({
                    'product': product,
                    'score': min(score, 1.0)  # Cap at 1.0
                })
            
            # Sort by score descending
            scored_products.sort(key=lambda x: x['score'], reverse=True)
            
            return scored_products[:limit]
            
        except Exception as e:
            logger.error(f"Error in _get_content_based_for_user: {e}", exc_info=True)
            return []

 