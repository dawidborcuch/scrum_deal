import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scrumdeal.settings')

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

# Importujemy routing po załadowaniu Django
def get_websocket_urlpatterns():
    from poker.routing import websocket_urlpatterns
    return websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": URLRouter(get_websocket_urlpatterns()),
}) 