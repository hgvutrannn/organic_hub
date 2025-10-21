from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db import models
from core.models import CustomUser, Product
from .models import Message

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
        return redirect('some_other_safe_page') # Hoặc xử lý lỗi
    
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
