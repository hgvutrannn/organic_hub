from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db import models
from django.http import JsonResponse
from core.models import CustomUser, Product
from .models import Message

@login_required
def private_room(request, user_id):
    """
    DEPRECATED: This view is deprecated. Chat functionality is now handled by the floating chat widget.
    Redirects to home page where chat widget will be available.
    """
    # Redirect to home - chat widget will handle the chat functionality
    return redirect('home')

@login_required
def chat_list(request):
    """
    DEPRECATED: This view is deprecated. Chat functionality is now handled by the floating chat widget.
    Redirects to home page where chat widget will be available.
    """
    # Redirect to home - chat widget will handle the chat functionality
    return redirect('home')

@login_required
def chat_rooms_api(request):
    """API endpoint to get chat rooms list for floating widget"""
    user = request.user
    
    # Get all messages related to user
    messages = Message.objects.filter(
        models.Q(sender=user) | models.Q(recipient=user)
    ).order_by('-created_at')
    
    # Count unread messages
    unread_counts = {}
    unread_messages = Message.objects.filter(
        recipient=user,
        is_read=False
    )
    for msg in unread_messages:
        room_name = msg.room_name
        if room_name not in unread_counts:
            unread_counts[room_name] = 0
        unread_counts[room_name] += 1
    
    # Group messages by room_name
    chat_rooms = {}
    
    for message in messages:
        room_name = message.room_name
        if room_name not in chat_rooms:
            # Identify the user chatting with
            if message.sender == user:
                other_user = message.recipient
            else:
                other_user = message.sender
            
            user_ids = sorted([user.user_id, other_user.user_id])
            room_data = {
                'room_name': room_name,
                'other_user': {
                    'user_id': other_user.user_id,
                    'full_name': other_user.full_name or other_user.email,
                    'email': other_user.email,
                    'avatar': other_user.avatar.url if other_user.avatar else None,
                },
                'last_message': {
                    'content': message.content,
                    'created_at': message.created_at.isoformat(),
                    'sender_id': message.sender.user_id,
                },
                'unread_count': unread_counts.get(room_name, 0),
            }
            
            chat_rooms[room_name] = room_data
    
    # Sort by time
    all_rooms = sorted(
        chat_rooms.values(),
        key=lambda x: x['last_message']['created_at'] if x['last_message']['created_at'] else '',
        reverse=True
    )
    
    return JsonResponse({
        'chat_rooms': all_rooms,
        'total_unread': sum(unread_counts.values())
    })

@login_required
def chat_messages_api(request, user_id):
    """API endpoint to get messages of a chat"""
    other_user = get_object_or_404(CustomUser, user_id=user_id)
    
    if request.user.user_id == user_id:
        return JsonResponse({'error': 'Cannot chat with yourself'}, status=400)
    
    # Build room name
    user_ids = sorted([request.user.user_id, other_user.user_id])
    room_name = f"chat_{user_ids[0]}_{user_ids[1]}"
    
    # Get chat history
    messages = Message.objects.filter(
        room_name=room_name
    ).order_by('created_at').select_related('sender', 'recipient')
    
    messages_data = []
    for msg in messages:
        messages_data.append({
            'message_id': msg.message_id,
            'sender_id': msg.sender.user_id,
            'sender_name': msg.sender.full_name or msg.sender.phone_number,
            'sender_avatar': msg.sender.avatar.url if msg.sender.avatar else None,
            'content': msg.content,
            'created_at': msg.created_at.isoformat(),
            'is_read': msg.is_read,
        })
    
    return JsonResponse({
        'room_name': room_name,
        'other_user': {
            'user_id': other_user.user_id,
            'full_name': other_user.full_name or other_user.email,
            'email': other_user.email,
            'avatar': other_user.avatar.url if other_user.avatar else None,
        },
        'messages': messages_data
    })


@login_required
@require_POST
def mark_message_read(request, other_user_id):
    # Mark all unread messages in a room as read
    other_user = get_object_or_404(CustomUser, user_id=other_user_id)
    # Build room name
    user_ids = sorted([request.user.user_id, other_user.user_id])
    room_name = f"chat_{user_ids[0]}_{user_ids[1]}"    

    updated = Message.objects.filter(
        room_name=room_name,
        recipient=request.user,
        is_read=False
    ).update(is_read=True)

    return JsonResponse({
        'success': True,
        'updated': updated,
    })


@login_required
@require_POST
def init_chat_room(request, user_id):
    """Send product inquiry message to store owner and return room info"""
    store_owner = get_object_or_404(CustomUser, user_id=user_id)
    current_user = request.user
    
    # Prevent chatting with yourself
    if current_user.user_id == user_id:
        return JsonResponse({'error': 'Cannot chat with yourself'}, status=400)
    
    # Build room name (same format as chat system uses)
    user_ids = sorted([current_user.user_id, store_owner.user_id])
    room_name = f"chat_{user_ids[0]}_{user_ids[1]}"
    
    # Get product name from query params
    product_name = request.GET.get('product_name', 'this product')
    
    # Always create a new message about the product
    initial_message = f"Hi, I'm interested about {product_name}. Can you tell me more about this?"
    Message.objects.create(
        sender=current_user,
        recipient=store_owner,
        content=initial_message,
        room_name=room_name
    )
    
    return JsonResponse({
        'success': True,
        'room_name': room_name,
        'other_user': {
            'user_id': store_owner.user_id,
            'full_name': store_owner.full_name or store_owner.email,
            'email': store_owner.email,
            'avatar': store_owner.avatar.url if store_owner.avatar else None,
        }
    })