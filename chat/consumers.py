# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import ChatUser, ChatMessage
from channels.db import database_sync_to_async


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f"chat_{self.room_name}"

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']
        sender_id = data['sender_id']
        receiver_id = data['receiver_id']

        saved_msg = await self.save_message(sender_id, receiver_id, message)

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'sender_id': sender_id,
                'receiver_id': receiver_id,
                'timestamp': str(saved_msg.timestamp),
                'status': saved_msg.status,
                'msg_id': saved_msg.id,
            }
           )
        
        # elif action == "mark_read":
        #     reader_id = data['reader_id']
        #     sender_id = data['sender_id']
        #     await self.mark_messages_read(sender_id, reader_id)

        #     # Notify sender to update tick marks to "read"
        #     await self.channel_layer.group_send(
        #         self.room_group_name,
        #         {
        #             'type': 'read_update',
        #             'reader_id': reader_id,
        #             'sender_id': sender_id,
        #         }
        #     )

    # Receive message from room group
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender_id': event['sender_id'],
            'receiver_id': event['receiver_id'],
            'timestamp': event['timestamp'],
            'status': event['status'],
            'msg_id': event['msg_id'],
        }))

    @database_sync_to_async
    def save_message(self, sender_id, receiver_id, message):
        sender = ChatUser.objects.get(id=sender_id)
        receiver = ChatUser.objects.get(id=receiver_id)
        return ChatMessage.objects.create(
            sender=sender,
            receiver=receiver,
            content=message,
            status='sent'
        )
        
    @database_sync_to_async
    def mark_messages_delivered(self, user):
        # Get unread messages sent to this user
        messages = ChatMessage.objects.filter(
            receiver=user,
            status='sent'
        )
        messages.update(status='delivered')        