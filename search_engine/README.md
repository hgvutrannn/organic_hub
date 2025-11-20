# Search Engine App - Elasticsearch Integration

This Django app provides Elasticsearch integration for product search functionality.

## Features

- **Field Boosting**: Name field has 3x boost compared to description (name^3, description^1)
- **Automatic Fallback**: Falls back to Django ORM search if Elasticsearch is unavailable
- **Auto-indexing**: Automatically indexes products when created/updated/deleted
- **Non-breaking**: Original Django ORM search code is preserved as fallback

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Start Elasticsearch

Using Docker Compose:
```bash
docker-compose up -d elasticsearch
```

Or manually:
```bash
docker run -d -p 9200:9200 -p 9300:9300 -e "discovery.type=single-node" docker.elastic.co/elasticsearch/elasticsearch:7.17.0
```

### 3. Configure Settings

The app uses environment variables for configuration (with defaults):

- `USE_ELASTICSEARCH`: Enable/disable Elasticsearch (default: True)
- `ELASTICSEARCH_HOST`: Elasticsearch host (default: localhost)
- `ELASTICSEARCH_PORT`: Elasticsearch port (default: 9200)
- `ELASTICSEARCH_USE_SSL`: Use SSL (default: False)
- `ELASTICSEARCH_VERIFY_CERTS`: Verify SSL certificates (default: True)
- `ELASTICSEARCH_TIMEOUT`: Connection timeout in seconds (default: 30)

### 4. Build Search Index

After starting Elasticsearch, build the index with all existing products:

```bash
python manage.py build_search_index
```

Or rebuild from scratch:

```bash
python manage.py rebuild_search_index
```

## Management Commands

### Build Search Index

Index all active products:

```bash
python manage.py build_search_index
```

Options:
- `--batch-size`: Number of products to index per batch (default: 100)

### Rebuild Search Index

Delete and recreate the index:

```bash
python manage.py rebuild_search_index
```

Options:
- `--batch-size`: Number of products to index per batch (default: 100)

### Update Search Index

Update specific product or all products:

```bash
# Update single product
python manage.py update_search_index --product-id <product_id>

# Update all products
python manage.py update_search_index --all
```

Options:
- `--product-id`: Update specific product by ID
- `--all`: Update all products
- `--batch-size`: Batch size for --all option (default: 100)

## Usage

### In Views

The `product_list` view automatically uses Elasticsearch if enabled:

```python
# Elasticsearch is used automatically if USE_ELASTICSEARCH=True
# Falls back to Django ORM if Elasticsearch fails
```

### Direct Usage

```python
from search_engine.services import ProductSearchService

# Search with Elasticsearch (with fallback)
products = ProductSearchService.search_with_fallback(
    query="rau củ",
    filters={'category_id': 1, 'min_price': 10000},
    use_elasticsearch=True
)

# Direct Elasticsearch search (no fallback)
products = ProductSearchService.search(
    query="rau củ",
    filters={'category_id': 1}
)
```

## Field Boosting

The search uses field boosting to prioritize name over description:

- **name**: Boost factor of 3 (name^3)
- **description**: Boost factor of 1 (description^1)

This means products with the search term in the name will rank higher than those with it only in the description.

## Auto-indexing

Products are automatically indexed when:
- Created (if `is_active=True`)
- Updated (if `is_active` changes)
- Deleted (removed from index)

This is handled by Django signals in `signals.py`.

## Disabling Elasticsearch

To disable Elasticsearch and use Django ORM search only:

1. Set environment variable: `USE_ELASTICSEARCH=False`
2. Or in settings: `USE_ELASTICSEARCH = False`

## Troubleshooting

### Elasticsearch Connection Error

If you see connection errors:
1. Check if Elasticsearch is running: `curl http://localhost:9200`
2. Verify environment variables are set correctly
3. Check firewall settings

### Index Not Found

If you get index not found errors:
1. Run `python manage.py build_search_index` to create the index
2. Check Elasticsearch logs: `docker logs organic_hub_elasticsearch`

### Products Not Appearing in Search

1. Verify products are indexed: Check Elasticsearch directly
2. Rebuild index: `python manage.py rebuild_search_index`
3. Check if products have `is_active=True`

## API Endpoint

The app provides an API endpoint for AJAX search requests:

```
GET /search/api/?q=<query>&category_id=<id>&min_price=<price>&max_price=<price>
```

Returns JSON with product results.

## Architecture

- **documents.py**: Defines ProductDocument for Elasticsearch
- **services.py**: ProductSearchService with search logic and fallback
- **signals.py**: Auto-indexing on Product model changes
- **management/commands/**: Commands for index management
- **config.py**: Elasticsearch configuration

## Performance

- **Elasticsearch**: 5-30x faster than Django ORM for large datasets
- **Relevance**: Better ranking with field boosting
- **Scalability**: Handles millions of products efficiently

