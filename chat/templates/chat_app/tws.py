ASGI_APPLICATION = 'chat_app.asgi.application'


# Channel layer (for WebSocket communication)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    },
}

======================= asgi.py ========================
# asgi.py (project level)

import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack 
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application
import chat.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chat_app.settings')
django.setup()

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
        URLRouter(
            chat.routing.websocket_urlpatterns
        ))
    ),
})




<script>
    const roomName = "{{ room_name }}";
    const sender = "{{ current_user.id }}";
    const receiver = "{{ receiver.id }}";

    const chatSocket = new WebSocket(
        'ws://' + window.location.host + '/ws/chat/' + roomName + '/'
    );

    chatSocket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        const message = data.message;
        const senderId = data.sender;

        const newMsg = document.createElement('div');
        newMsg.className = senderId == sender ? 'message sent' : 'message received';
        newMsg.style.cssText = `
            margin-bottom:12px;max-width:70%;padding:10px 16px;border-radius:18px;clear:both;
            ${senderId == sender
                ? 'background:#dcf8c6;margin-left:auto;text-align:right;'
                : 'background:#fff;margin-right:auto;text-align:left;border:1px solid #ddd;'}
        `;
        newMsg.innerHTML = `<div>${message}</div>`;
        document.querySelector("#message-list").appendChild(newMsg);
    };

    chatSocket.onclose = function(e) {
        console.error('Socket closed unexpectedly');
    };

    document.querySelector("#chat-form").addEventListener("submit", function(e) {
        e.preventDefault();
        const input = document.querySelector("#chat-message-input");
        const message = input.value;
        chatSocket.send(JSON.stringify({
            'message': message,
            'sender': sender,
            'receiver': receiver
        }));
        input.value = '';
    });
</script>


# chat_app/routing.py

from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path("ws/chat/<str:room_name>/", consumers.ChatConsumer.as_asgi()),
]




# chat_app/consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']
        sender = data['sender']
        receiver = data['receiver']

        # Broadcast message to group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'sender': sender,
                'receiver': receiver,
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender'],
            'receiver': event['receiver'],
        }))






# from channels.generic.websocket import AsyncWebsocketConsumer
# import json

# class ChatConsumer(AsyncWebsocketConsumer):
#     async def connect(self):
#         print("Connect called")
#         self.room_name = self.scope['url_route']['kwargs']['room_name']
#         print(f"Room name: {self.room_name}")
#         self.room_group_name = f'room_{self.room_name}'

#         await self.channel_layer.group_add(
#             self.room_group_name,
#             self.channel_name
#         )

#         await self.accept()

#         print("Connection accepted")

#         await self.send(text_data=json.dumps({
#             'payload': 'connected'
#         }))

        
#     def receive(self, text_data ):
#         pass
    
#     def disconnect(self, close_code):
#         pass
#     # async def connect(self):
#     #     self.room_name = self.scope['url_route']['kwargs']['room_name']
#     #     self.room_group_name = f'chat_{self.room_name}'

#     #     # Join chat group
#     #     await self.channel_layer.group_add(
#     #         self.room_group_name,
#     #         self.channel_name
#     #     )
#     #     await self.accept()

#     # async def disconnect(self, close_code):
#     #     # Leave group
#     #     await self.channel_layer.group_discard(
#     #         self.room_group_name,
#     #         self.channel_name
#     #     )

#     # async def receive(self, text_data):
#     #     data = json.loads(text_data)
#     #     message = data['message']
#     #     sender_id = data['sender_id']
#     #     receiver_id = data['receiver_id']

#     #     print('Received message on websocket:', message, 'from', sender_id, 'to', receiver_id)

#     #     # Save message to database (must be async-safe)
#     #     sender = await sync_to_async(ChatUser.objects.get)(id=sender_id)
#     #     receiver = await sync_to_async(ChatUser.objects.get)(id=receiver_id)
#     #     chat_msg = await sync_to_async(ChatMessage.objects.create)(sender=sender, receiver=receiver, content=message)
#     #     print('Saved chat message id=', chat_msg.id)

#     #     # Broadcast to all users in the room
#     #     await self.channel_layer.group_send(
#     #         self.room_group_name,
#     #         {
#     #             'type': 'chat_message',
#     #             'message': message,
#     #             'sender_id': sender_id,
#     #             'receiver_id': receiver_id,
#     #             'timestamp': chat_msg.timestamp.isoformat(),
#     #         }
#     #     )
#     #     print('Group send to', self.room_group_name)

#     # async def chat_message(self, event):
#     #     await self.send(text_data=json.dumps({
#     #         'message': event['message'],
#     #         'sender_id': event['sender_id'],
#     #         'receiver_id': event['receiver_id'],
#     #         'timestamp': event.get('timestamp')
#     #     }))
