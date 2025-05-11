from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<chat_id>[^/]+)/$', consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/agent/notifications/$', consumers.AgentNotificationConsumer.as_asgi()),
    re_path(r'ws/debug/$', consumers.DebugConsumer.as_asgi()),
    re_path(r'ws/test/$', consumers.TestConsumer.as_asgi()),
] 