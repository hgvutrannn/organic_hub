"""
URLs for search_engine app
"""
from django.urls import path
from . import views

app_name = 'search_engine'

urlpatterns = [
    path('api/', views.search_api, name='search_api'),
    path('test/', views.test_search, name='test_search'),
    path('status/', views.elasticsearch_status, name='elasticsearch_status'),
]

