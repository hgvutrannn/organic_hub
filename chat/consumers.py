import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from core.models import CustomUser
from .models import Message
# from asgiref.sync import sync_to_async

class PrivateChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = self.room_name

        user = self.scope['user']
        if not user.is_authenticated:
            await self.close()
            return

        try: 
            _, id1_str, id2_str = self.room_name.split('_')
            id1, id2 = int(id1_str), int(id2_str)
        except ValueError:
            await self.close()
            return

        if user.user_id not in [id1, id2]:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        username = self.scope['user'].full_name
        sender_id = self.scope['user'].user_id

        # Lưu tin nhắn vào database
        await self.save_message_to_db(message, sender_id)

        # ✅ GỬI TIN NHẮN CHỈ ĐẾN USER KHÁC
        # Lấy danh sách user trong room
        _, id1_str, id2_str = self.room_name.split('_')
        id1, id2 = int(id1_str), int(id2_str)
        
        # Tìm user khác (không phải người gửi)
        other_user_id = id1 if sender_id == id2 else id2

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'username': username,
                'sender_id': self.scope['user'].user_id,
                'target_user_id': other_user_id,
            }
        )

    async def chat_message(self, event):
        current_user_id = self.scope['user'].user_id
        target_user_id = event.get('target_user_id')

        if current_user_id == target_user_id:
            await self.send(text_data=json.dumps({
                'message': event['message'],
                'username': event['username'],
                'sender_id': event['sender_id']
            }))

    @sync_to_async
    def save_message_to_db(self, content, sender_id):
        """Lưu tin nhắn vào database"""
        try:
            # Lấy thông tin sender và recipient
            sender = CustomUser.objects.get(user_id=sender_id)
            
            # Lấy danh sách user trong room để tìm recipient
            _, id1_str, id2_str = self.room_name.split('_')
            id1, id2 = int(id1_str), int(id2_str)
            
            # Tìm recipient (user khác trong room)
            recipient_id = id1 if sender_id == id2 else id2
            recipient = CustomUser.objects.get(user_id=recipient_id)
            
            # Tạo tin nhắn mới
            Message.objects.create(
                sender=sender,
                recipient=recipient,
                content=content,
                room_name=self.room_name
            )
        except Exception as e:
            print(f"Lỗi khi lưu tin nhắn: {e}")

        