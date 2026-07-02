import os

from config.load_env import load_env
from django.core.asgi import get_asgi_application

load_env()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.phase0')

# Django setup MUST complete before importing consumers (which import models).
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.auth import AuthMiddlewareStack  # noqa: E402
from django.urls import re_path  # noqa: E402

from infrastructure.ws.consumer import ProjectConsumer  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter([
            re_path(r"^ws/projects/(?P<project_id>[^/]+)/$", ProjectConsumer.as_asgi()),
        ])
    ),
})
