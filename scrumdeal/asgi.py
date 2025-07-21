import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scrumdeal.settings')

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": URLRouter(
        __import__('poker.routing').routing.websocket_urlpatterns
    ),
}) 