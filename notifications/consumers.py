from channels.generic.websocket import AsyncJsonWebsocketConsumer


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """WebSocket consumer that streams realtime notifications to a user."""

    async def connect(self):
        user = self.scope.get('user')
        if user is None or user.is_anonymous:
            await self.close()
            return

        self.user = user
        self.group_name = f'notifications_{user.user_id}'

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def notification_message(self, event):
        payload = event.get('payload', {})
        await self.send_json(payload)
