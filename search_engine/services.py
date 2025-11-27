"""
Product search service using Elasticsearch
"""
import logging
from typing import List, Optional, Dict, Any
from django.conf import settings
from django_elasticsearch_dsl import Document
from elasticsearch_dsl import Q, Search
from core.models import Product
from .documents import ProductDocument

logger = logging.getLogger(__name__)


class ProductSearchService:
    """
    Service for searching products using Elasticsearch
    Supports field boosting (name^3, description^1)
    """

    @staticmethod
    def search(
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        size: int = 100
    ) -> List[Product]:
        """
        Search products using Elasticsearch
        
        Args:
            query: Search query string
            filters: Optional filters dict with keys:
                - category_id: Filter by category
                - certificate_id: Filter by certification organization ID (NEW)
                - min_price: Minimum price
                - max_price: Maximum price
                - store_id: Filter by store
                - is_active: Filter by active status
            size: Maximum number of results
        
        Returns:
            List of Product objects ordered by relevance score
        """
        try:
            logger.debug(f"Building Elasticsearch query for: '{query}'")
            search = ProductDocument.search()
            
            # Multi-match query with field boosting
            if query:
                search = search.query(
                    'multi_match',
                    query=query,
                    fields=['name^3', 'description^1'],
                    type='best_fields',
                    fuzziness='AUTO'
                )
                logger.debug(f"Built multi_match query for: '{query}'")
            else:
                search = search.query('match_all')
                logger.debug("Built match_all query")
            
            # Apply filters
            if filters:
                filter_queries = []
                
                if filters.get('category_id'):
                    filter_queries.append(
                        Q('term', category_id=filters['category_id'])
                    )
                
                # THÊM FILTER NÀY
                if filters.get('certificate_id'):
                    # Sử dụng 'terms' query để match với bất kỳ giá trị nào trong array
                    filter_queries.append(
                        Q('terms', certification_organization_ids=[filters['certificate_id']])
                    )
                
                if filters.get('store_id'):
                    filter_queries.append(
                        Q('term', store_id=filters['store_id'])
                    )
                
                if filters.get('is_active') is not None:
                    filter_queries.append(
                        Q('term', is_active=filters['is_active'])
                    )
                
                if filters.get('min_price') is not None or filters.get('max_price') is not None:
                    price_range = {}
                    if filters.get('min_price') is not None:
                        price_range['gte'] = float(filters['min_price'])
                    if filters.get('max_price') is not None:
                        price_range['lte'] = float(filters['max_price'])
                    filter_queries.append(Q('range', price=price_range))
                
                if filter_queries:
                    search = search.filter(Q('bool', must=filter_queries))
            
            # Set size and execute search
            search = search[:size]
            response = search.execute()
            
            # Extract Product IDs from search results
            product_ids = [hit.product_id for hit in response]
            
            # Fetch Product objects from database in the same order
            products = Product.objects.filter(product_id__in=product_ids).select_related('category', 'store')
            
            # Create a dictionary for O(1) lookup
            product_dict = {p.product_id: p for p in products}
            
            # Return products in the same order as search results
            return [product_dict[pid] for pid in product_ids if pid in product_dict]
            
        except Exception as e:
            logger.error(f"Elasticsearch search error: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def search_with_fallback(
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        size: int = 100,
        use_elasticsearch: bool = True
    ) -> List[Product]:
        """
        Search products with fallback to Django ORM if Elasticsearch fails
        
        Args:
            query: Search query string
            filters: Optional filters dict
            size: Maximum number of results
            use_elasticsearch: Whether to use Elasticsearch (default: True)
        
        Returns:
            List of Product objects
        """
        # Check if Elasticsearch is enabled
        if not use_elasticsearch:
            return ProductSearchService._fallback_search(query, filters, size)
        
        try:
            # Try Elasticsearch search
            logger.debug(f"Attempting Elasticsearch search: query='{query}', filters={filters}")
            result = ProductSearchService.search(query, filters, size)
            logger.info(f"Elasticsearch search successful: found {len(result)} products")
            return result
        except Exception as e:
            logger.warning(f"Elasticsearch search failed, falling back to Django ORM: {str(e)}")
            logger.exception(e)  # Log full traceback
            # Fallback to Django ORM search
            return ProductSearchService._fallback_search(query, filters, size)

    @staticmethod
    def _fallback_search(
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        size: int = 100
    ) -> List[Product]:
        """
        Fallback search using Django ORM (original search method)
        """
        from django.db.models import Q
        
        products = Product.objects.filter(is_active=True)
        
        # Apply text search
        if query:
            products = products.filter(
                Q(name__icontains=query) | Q(description__icontains=query)
            )
        
        # Apply filters
        if filters:
            if filters.get('category_id'):
                products = products.filter(category_id=filters['category_id'])
            
            # THÊM FILTER NÀY
            if filters.get('certificate_id'):
                # Filter products có Store với CertificationOrganization này
                products = products.filter(
                    store__verification_requests__certifications__certification_organization_id=filters['certificate_id']
                ).distinct()
            
            if filters.get('store_id'):
                products = products.filter(store_id=filters['store_id'])
            
            if filters.get('is_active') is not None:
                products = products.filter(is_active=filters['is_active'])
            
            if filters.get('min_price') is not None:
                products = products.filter(price__gte=filters['min_price'])
            
            if filters.get('max_price') is not None:
                products = products.filter(price__lte=filters['max_price'])
        
        # Order by view_count and created_at
        products = products.order_by('-view_count', '-created_at')
        
        return list(products[:size])

