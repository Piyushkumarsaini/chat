import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import ChatUser, ChatMessage
from asgiref.sync import sync_to_async
import logging

logger = logging.getLogger(__name__)

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'

        # Join chat group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']
        sender_id = data['sender_id']
        receiver_id = data['receiver_id']

        print('Received message on websocket:', message, 'from', sender_id, 'to', receiver_id)

        # Save message to database (must be async-safe)
        sender = await sync_to_async(ChatUser.objects.get)(id=sender_id)
        receiver = await sync_to_async(ChatUser.objects.get)(id=receiver_id)
        chat_msg = await sync_to_async(ChatMessage.objects.create)(sender=sender, receiver=receiver, content=message)
        print('Saved chat message id=', chat_msg.id)

        # Broadcast to all users in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'sender_id': sender_id,
                'receiver_id': receiver_id,
                'timestamp': chat_msg.timestamp.isoformat(),
            }
        )
        print('Group send to', self.room_group_name)

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender_id': event['sender_id'],
            'receiver_id': event['receiver_id'],
            'timestamp': event.get('timestamp')
        }))
