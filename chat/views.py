from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import JsonResponse
from core.models import CustomUser, Product
from .models import Message
from .bot import OrderBot

@login_required
def private_room(request, user_id):
    # 1. Kiểm tra User tồn tại
    
    other_user = get_object_or_404(CustomUser, user_id=user_id)
    
    print(other_user)
    # 2. Xây dựng Tên Group (Group Name Deterministic)
    # Luôn sắp xếp ID người dùng để đảm bảo tên Group duy nhất
    user_ids = sorted([request.user.user_id, other_user.user_id])
    room_name = f"chat_{user_ids[0]}_{user_ids[1]}"
    
    # Nếu người dùng cố gắng chat với chính mình
    if request.user.user_id == user_id:
        return redirect('chat_list')
    
    # Lấy lịch sử chat từ database
    chat_history = Message.objects.filter(
        room_name=room_name
    ).order_by('created_at')
    
    return render(request, 'chat/private_room.html', {
        'room_name': room_name,
        'other_user': other_user,
        'chat_history': chat_history,
    })

@login_required
def chat_list(request):
    """Hiển thị danh sách tất cả cuộc chat của user"""
    user = request.user
    
    # Lấy tất cả tin nhắn liên quan đến user (gửi hoặc nhận)
    messages = Message.objects.filter(
        models.Q(sender=user) | models.Q(recipient=user)
    ).order_by('-created_at')
    
    # Nhóm tin nhắn theo room_name để tạo danh sách chat
    chat_rooms = {}
    for message in messages:
        room_name = message.room_name
        if room_name not in chat_rooms:
            # Xác định người chat với user
            if message.sender == user:
                other_user = message.recipient
            else:
                other_user = message.sender
            
            chat_rooms[room_name] = {
                'other_user': other_user,
                'last_message': message,
                'room_name': room_name
            }
    
    return render(request, 'chat/chat_list.html', {
        'chat_rooms': list(chat_rooms.values())
    })

@login_required
def chat_rooms_api(request):
    """API endpoint để lấy danh sách chat rooms cho floating widget"""
    user = request.user
    
    # Lấy tất cả tin nhắn liên quan đến user
    messages = Message.objects.filter(
        models.Q(sender=user) | models.Q(recipient=user)
    ).order_by('-created_at')
    
    # Đếm số tin nhắn chưa đọc
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
    
    # Nhóm tin nhắn theo room_name
    chat_rooms = {}
    bot_room = None
    
    for message in messages:
        room_name = message.room_name
        if room_name not in chat_rooms:
            # Xác định người chat với user
            if message.sender == user:
                other_user = message.recipient
            else:
                other_user = message.sender
            
            user_ids = sorted([user.user_id, other_user.user_id])
            room_data = {
                'room_name': room_name,
                'other_user': {
                    'user_id': other_user.user_id,
                    'full_name': other_user.full_name or other_user.phone_number,
                    'phone_number': other_user.phone_number,
                    'avatar': other_user.avatar.url if other_user.avatar else None,
                },
                'last_message': {
                    'content': message.content,
                    'created_at': message.created_at.isoformat(),
                    'sender_id': message.sender.user_id,
                },
                'unread_count': unread_counts.get(room_name, 0),
                'is_bot': OrderBot.is_bot_room(room_name),
            }
            
            # Tách bot room ra
            if room_data['is_bot']:
                bot_room = room_data
            else:
                chat_rooms[room_name] = room_data
    
    # Nếu chưa có bot room, tạo một
    if not bot_room:
        bot_user = OrderBot.get_or_create_bot_user()
        bot_room_name = OrderBot.get_bot_room_name(user.user_id)
        bot_room = {
            'room_name': bot_room_name,
            'other_user': {
                'user_id': bot_user.user_id,
                'full_name': bot_user.full_name or OrderBot.BOT_DISPLAY_NAME,
                'phone_number': bot_user.phone_number,
                'avatar': bot_user.avatar.url if bot_user.avatar else None,
            },
            'last_message': {
                'content': '',
                'created_at': None,
                'sender_id': bot_user.user_id,
            },
            'unread_count': 0,
            'is_bot': True,
        }
    
    # Sắp xếp: bot room luôn ở đầu, sau đó các room khác theo thời gian
    other_rooms = sorted(
        chat_rooms.values(),
        key=lambda x: x['last_message']['created_at'] if x['last_message']['created_at'] else '',
        reverse=True
    )
    
    # Bot room luôn ở đầu
    all_rooms = [bot_room] + other_rooms
    
    return JsonResponse({
        'chat_rooms': all_rooms,
        'total_unread': sum(unread_counts.values())
    })

@login_required
def chat_messages_api(request, user_id):
    """API endpoint để lấy tin nhắn của một cuộc chat"""
    other_user = get_object_or_404(CustomUser, user_id=user_id)
    
    if request.user.user_id == user_id:
        return JsonResponse({'error': 'Cannot chat with yourself'}, status=400)
    
    # Xây dựng room name
    user_ids = sorted([request.user.user_id, other_user.user_id])
    room_name = f"chat_{user_ids[0]}_{user_ids[1]}"
    
    # Lấy lịch sử chat
    messages = Message.objects.filter(
        room_name=room_name
    ).order_by('created_at').select_related('sender', 'recipient')
    
    messages_data = []
    for msg in messages:
        messages_data.append({
            'message_id': msg.message_id,
            'sender_id': msg.sender.user_id,
            'sender_name': msg.sender.full_name or msg.sender.phone_number,
            'content': msg.content,
            'created_at': msg.created_at.isoformat(),
            'is_read': msg.is_read,
        })
    
    return JsonResponse({
        'room_name': room_name,
        'other_user': {
            'user_id': other_user.user_id,
            'full_name': other_user.full_name or other_user.phone_number,
            'phone_number': other_user.phone_number,
            'avatar': other_user.avatar.url if other_user.avatar else None,
        },
        'messages': messages_data
    })


@login_required
def bot_chat_room(request):
    """Tạo hoặc lấy room chat với bot"""
    bot_user = OrderBot.get_or_create_bot_user()
    room_name = OrderBot.get_bot_room_name(request.user.user_id)
    
    # Lấy lịch sử chat
    chat_history = Message.objects.filter(
        room_name=room_name
    ).order_by('created_at')
    
    return render(request, 'chat/private_room.html', {
        'room_name': room_name,
        'other_user': bot_user,
        'chat_history': chat_history,
        'is_bot': True,
    })
