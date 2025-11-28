import json
import logging
from typing import Dict
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.db import models
from core.models import CustomUser
from .models import Message

logger = logging.getLogger(__name__)


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
        user = self.scope['user']
        username = user.full_name or user.email or 'User'
        sender_id = user.user_id

        # Save message to database
        await self.save_message_to_db(message, sender_id)

        # ✅ SEND MESSAGE ONLY TO OTHER USER
        # Get list of users in room
        _, id1_str, id2_str = self.room_name.split('_')
        id1, id2 = int(id1_str), int(id2_str)
        
        # Find other user (not the sender)
        other_user_id = id1 if sender_id == id2 else id2

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'username': username,
                'sender_id': sender_id,
                'target_user_id': other_user_id,
            }
        )

    async def chat_message(self, event):
        current_user_id = self.scope['user'].user_id
        sender_id = event.get('sender_id')
        
        # Send message to all users in the room (both sender and recipient will receive it)
        # The frontend will filter to only show messages from others
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'username': event['username'],
            'sender_id': sender_id
        }))

    @sync_to_async
    def save_message_to_db(self, content, sender_id):
        """Save message to database"""
        try:
            # Get sender and recipient information
            sender = CustomUser.objects.get(user_id=sender_id)
            
            # Get list of users in room to find recipient
            _, id1_str, id2_str = self.room_name.split('_')
            id1, id2 = int(id1_str), int(id2_str)
            
            # Find recipient (other user in room)
            recipient_id = id1 if sender_id == id2 else id2
            recipient = CustomUser.objects.get(user_id=recipient_id)
            
            # Create new message
            Message.objects.create(
                sender=sender,
                recipient=recipient,
                content=content,
                room_name=self.room_name
            )
        except Exception as e:
            print(f"Error saving message: {e}")


