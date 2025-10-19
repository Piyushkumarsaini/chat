from django.utils import timezone
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import ChatUser, ChatMessage
from channels.db import database_sync_to_async


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f"chat_{self.room_name}"

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)


    # Receive message from WebSocket
    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')
        
        if action == 'send_message':
            message = data.get('message')
            sender_id = data.get('sender_id')
            receiver_id = data.get('receiver_id')
            
            if not (message and sender_id and receiver_id):
                # invalid payload
                return
            
            
            saved_msg = await self.save_message(sender_id, receiver_id, message)

            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': saved_msg.content,
                    'sender_id': saved_msg.sender.id,
                    'receiver_id': saved_msg.receiver.id,
                    'timestamp': str(saved_msg.timestamp),
                    'status': saved_msg.status,
                    'msg_id': saved_msg.id,
                }
            )
            
        elif action == 'receiver_connected':
            # receiver_id tells server which user just connected (so we mark messages delivered)
            receiver_id = data.get('receiver_id')
            if not receiver_id:
                return

            delivered_ids = await self.mark_messages_delivered(receiver_id)
            if delivered_ids:
                # notify the room about status updates
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'status_update',
                        'msg_ids': delivered_ids,
                        'new_status': 'delivered',
                    }
                )
                
        elif action == 'mark_read':
            # reader_id is the user who read; other_user_id is the conversation partner (sender of messages)
            reader_id = data.get('reader_id')
            other_user_id = data.get('other_user_id')
            if not (reader_id and other_user_id):
                return

            read_ids = await self.mark_messages_read(reader_id, other_user_id)
            if read_ids:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'status_update',
                        'msg_ids': read_ids,
                        'new_status': 'read',
                    }
                )
    # Handlers for group events
    async def chat_message(self, event):
        # forward new message to WebSocket client
        await self.send(text_data=json.dumps({
            'event': 'chat_message',
            'message': event['message'],
            'sender_id': event['sender_id'],
            'receiver_id': event['receiver_id'],
            'timestamp': event['timestamp'],
            'status': event['status'],
            'msg_id': event['msg_id'],
        }))
        
        
    async def status_update(self, event):
        # forward status update (list of msg ids + new status)
        await self.send(text_data=json.dumps({
            'event': 'status_update',
            'msg_ids': event.get('msg_ids', []),
            'new_status': event.get('new_status'),
        }))
        
        
    # Database helpers (sync -> async)
    @database_sync_to_async
    def save_message(self, sender_id, receiver_id, message):
        sender = ChatUser.objects.get(id=sender_id)
        receiver = ChatUser.objects.get(id=receiver_id)
        msg = ChatMessage.objects.create(
            sender=sender,
            receiver=receiver,
            content=message,
            status='sent'
        )
        return msg
        
    @database_sync_to_async
    def mark_messages_delivered(self, receiver_id):
        """
        Mark all messages where receiver=receiver_id and status='sent' -> 'delivered'.
        Return list of updated message ids.
        """
        qs = ChatMessage.objects.filter(receiver_id=receiver_id, status='sent')
        ids = list(qs.values_list('id', flat=True))
        if ids:
            now = timezone.now()
            qs.update(status='delivered', delivered_at=now)
        return ids


    @database_sync_to_async
    def mark_messages_read(self, reader_id, other_user_id):
        """
        Mark messages sent by other_user_id to reader_id as 'read' (if not already read).
        Return list of updated message ids.
        """
        qs = ChatMessage.objects.filter(sender_id=other_user_id, receiver_id=reader_id).exclude(status='read')
        ids = list(qs.values_list('id', flat=True))
        if ids:
            now = timezone.now()
            qs.update(status='read', seen_at=now)
        return ids