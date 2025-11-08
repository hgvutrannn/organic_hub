"""
ASGI config for organic_hub project.
"""

import os
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from chat import routing as chat_routing
from notifications import routing as notifications_routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'organic_hub.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),

    "websocket": AuthMiddlewareStack(
        URLRouter(
            [
                *chat_routing.websocket_urlpatterns,
                *notifications_routing.websocket_urlpatterns,
            ]
        )
    ),
})
