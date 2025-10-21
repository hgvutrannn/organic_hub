from django.urls import path
from . import views

urlpatterns = [
    # ... các URLs khác
    path('private/<int:user_id>/', views.private_room, name='private_room'),
    path('list/', views.chat_list, name='chat_list'),
]