"""
Elasticsearch configuration
"""
import os
from django.conf import settings

# Elasticsearch connection settings
ELASTICSEARCH_HOST = os.getenv('ELASTICSEARCH_HOST', 'localhost')
ELASTICSEARCH_PORT = int(os.getenv('ELASTICSEARCH_PORT', '9200'))
ELASTICSEARCH_USE_SSL = os.getenv('ELASTICSEARCH_USE_SSL', 'False').lower() == 'true'
ELASTICSEARCH_VERIFY_CERTS = os.getenv('ELASTICSEARCH_VERIFY_CERTS', 'True').lower() == 'true'
ELASTICSEARCH_TIMEOUT = int(os.getenv('ELASTICSEARCH_TIMEOUT', '30'))

# Elasticsearch connection URL
ELASTICSEARCH_URL = f"{'https' if ELASTICSEARCH_USE_SSL else 'http'}://{ELASTICSEARCH_HOST}:{ELASTICSEARCH_PORT}"

