import os
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.urls import path
from chat.consumers import ChatConsumer  # update with your actual app

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chat_app.settings')

django_asgi_app = get_asgi_application()

ws_patterns = [
    path('chat/<room_name>', ChatConsumer.as_asgi())
]

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        URLRouter(ws_patterns)
    ),
})
