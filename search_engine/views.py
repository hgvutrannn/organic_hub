"""
Views for search_engine app
"""
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings
from .services import ProductSearchService

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def search_api(request):
    """
    API endpoint for product search
    Can be used for AJAX search requests
    """
    query = request.GET.get('q', '')
    category_id = request.GET.get('category_id')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    
    filters = {}
    if category_id:
        filters['category_id'] = int(category_id)
    if min_price:
        filters['min_price'] = float(min_price)
    if max_price:
        filters['max_price'] = float(max_price)
    
    try:
        products = ProductSearchService.search_with_fallback(query, filters)
        results = [
            {
                'product_id': p.product_id,
                'name': p.name,
                'price': float(p.price),
                'image_url': p.get_primary_image.url if p.get_primary_image else None,
            }
            for p in products[:20]  # Limit to 20 results for API
        ]
        return JsonResponse({'results': results, 'count': len(results)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def test_search(request):
    """
    Test endpoint to verify Elasticsearch is being used
    Returns detailed information about search method used
    """
    from django.db import connection
    from django.db import reset_queries
    
    query = request.GET.get('q', '')
    use_elasticsearch = getattr(settings, 'USE_ELASTICSEARCH', True)
    
    # Reset query count
    reset_queries()
    initial_query_count = len(connection.queries)
    
    result = {
        'query': query,
        'elasticsearch_enabled': use_elasticsearch,
        'search_method': None,
        'results_count': 0,
        'database_queries': 0,
        'execution_time_ms': 0,
        'error': None,
    }
    
    import time
    start_time = time.time()
    
    try:
        if use_elasticsearch:
            # Try Elasticsearch first
            try:
                products = ProductSearchService.search(query, {'is_active': True}, size=100)
                result['search_method'] = 'Elasticsearch'
                result['results_count'] = len(products)
            except Exception as e:
                logger.warning(f"Elasticsearch failed: {str(e)}")
                # Fallback to Django ORM
                products = ProductSearchService._fallback_search(query, {'is_active': True}, size=100)
                result['search_method'] = 'Django ORM (Fallback)'
                result['results_count'] = len(products)
                result['error'] = f'Elasticsearch error: {str(e)}'
        else:
            # Use Django ORM directly
            products = ProductSearchService._fallback_search(query, {'is_active': True}, size=100)
            result['search_method'] = 'Django ORM (Elasticsearch disabled)'
            result['results_count'] = len(products)
        
        execution_time = (time.time() - start_time) * 1000
        result['execution_time_ms'] = round(execution_time, 2)
        
        # Count database queries
        result['database_queries'] = len(connection.queries) - initial_query_count
        
        # Add sample results
        result['sample_results'] = [
            {
                'product_id': p.product_id,
                'name': p.name,
                'price': float(p.price),
            }
            for p in products[:5]
        ]
        
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"Search test error: {str(e)}", exc_info=True)
    
    return JsonResponse(result, json_dumps_params={'indent': 2})


@require_http_methods(["GET"])
def elasticsearch_status(request):
    """
    Check Elasticsearch connection status
    """
    from elasticsearch import Elasticsearch
    from search_engine.config import ELASTICSEARCH_URL
    
    result = {
        'elasticsearch_url': ELASTICSEARCH_URL,
        'connected': False,
        'cluster_health': None,
        'index_exists': False,
        'index_doc_count': 0,
        'error': None,
    }
    
    try:
        es = Elasticsearch([ELASTICSEARCH_URL], timeout=5)
        
        # Check connection
        if es.ping():
            result['connected'] = True
            
            # Get cluster health
            health = es.cluster.health()
            result['cluster_health'] = {
                'status': health.get('status'),
                'number_of_nodes': health.get('number_of_nodes'),
                'number_of_data_nodes': health.get('number_of_data_nodes'),
            }
            
            # Check if products index exists
            from search_engine.documents import ProductDocument
            index_name = ProductDocument._index._name
            
            if es.indices.exists(index=index_name):
                result['index_exists'] = True
                # Get document count
                stats = es.count(index=index_name)
                result['index_doc_count'] = stats.get('count', 0)
            else:
                result['index_exists'] = False
        else:
            result['error'] = 'Cannot ping Elasticsearch server'
            
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"Elasticsearch status check error: {str(e)}", exc_info=True)
    
    return JsonResponse(result, json_dumps_params={'indent': 2})
