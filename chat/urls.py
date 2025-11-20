from django.urls import path
from . import views

urlpatterns = [
    path('private/<int:user_id>/', views.private_room, name='private_room'),
    path('list/', views.chat_list, name='chat_list'),
    # Bot chat
    path('bot/', views.bot_chat_room, name='bot_chat_room'),
    # API endpoints for floating chat widget
    path('api/rooms/', views.chat_rooms_api, name='chat_rooms_api'),
    path('api/messages/<int:user_id>/', views.chat_messages_api, name='chat_messages_api'),
]