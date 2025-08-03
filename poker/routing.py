from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/poker/(?P<table_name>\w+)/$', consumers.PokerConsumer.as_asgi()),
    re_path(r'ws/home/$', consumers.HomeConsumer.as_asgi()),
] 