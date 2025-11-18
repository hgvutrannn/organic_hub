from django.urls import path

from . import views


app_name = 'notifications'

urlpatterns = [
    path('api/', views.notification_list, name='api_list'),
    path('api/<int:pk>/read/', views.mark_notification_read, name='mark_read'),
    path('api/mark-all-read/', views.mark_all_notifications_read, name='mark_all_read'),
]

