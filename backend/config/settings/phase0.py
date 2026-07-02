"""
Fase 0 — telas dummy sem serviços externos.
Inicia com: python manage.py runserver 3018
Não requer PostgreSQL, Redis, MinIO ou qualquer Docker externo.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-phase0-dev-only')
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

INSTALLED_APPS = [
    'daphne',  # first — overrides runserver to use ASGI/Daphne (WebSocket support)
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.staticfiles',
    'django.contrib.sessions',
    'django.contrib.messages',
    'channels',
    'django_htmx',
    'studio',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# SQLite local — apenas para sessions (sem ORM de domínio na Fase 0)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db_phase0.sqlite3',
    }
}

SESSION_ENGINE = 'django.contrib.sessions.backends.db'

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# Media (uploads locais na Fase 0 — MinIO na produção)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Upload limits
MAX_SOURCE_MB = 2048   # 2 GB por arquivo
ALLOWED_VIDEO_EXTS = ['mp4', 'mov', 'avi', 'mkv']

# F03/F04/F05 — merge + export + thumbnails
MERGE_SIMULATE     = os.environ.get('MERGE_SIMULATE', 'true').lower() != 'false'
HIGHLIGHT_SIMULATE = os.environ.get('HIGHLIGHT_SIMULATE', 'true').lower() != 'false'
EXPORT_SIMULATE    = os.environ.get('EXPORT_SIMULATE', 'true').lower() != 'false'
THUMBNAIL_SIMULATE = os.environ.get('THUMBNAIL_SIMULATE', 'true').lower() != 'false'
SEO_SIMULATE       = os.environ.get('SEO_SIMULATE', 'true').lower() != 'false'
PUBLISH_SIMULATE   = os.environ.get('PUBLISH_SIMULATE', 'true').lower() != 'false'
ANTHROPIC_API_KEY    = os.environ.get('ANTHROPIC_API_KEY', '')
GOOGLE_CLIENT_ID     = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
# Refresh token pré-gerado via scripts/get_youtube_token.py (dev mode sem redirect OAuth)
YOUTUBE_REFRESH_TOKEN = os.environ.get('YOUTUBE_REFRESH_TOKEN', '')
# Chave Fernet para criptografar tokens em prod (deixar vazio em dev = plain text)
OAUTH_ENCRYPTION_KEY  = os.environ.get('OAUTH_ENCRYPTION_KEY', '')

# F08 — Storage backend (opt-in via env: MinIO real do docker-compose.dev.yml,
# necessário para testar a ponte RabbitMQ↔highlight-worker — ver F17).
STORAGE_BACKEND  = os.environ.get('STORAGE_BACKEND', 'local')  # 'local' | 'minio'
MINIO_ENDPOINT   = os.environ.get('MINIO_ENDPOINT', '')        # ex.: http://localhost:9018
MINIO_ACCESS_KEY = os.environ.get('MINIO_ACCESS_KEY', '')
MINIO_SECRET_KEY = os.environ.get('MINIO_SECRET_KEY', '')
MINIO_BUCKET     = os.environ.get('MINIO_BUCKET', 'studio')

# F17 — ponte RabbitMQ com o highlight-worker externo (Whisper + Claude reais).
# Desligado por padrão: sem isso, o pipeline usa o adapter provisório (Claude
# direto sobre os picos de áudio, sem transcrição) — ver highlight_analyzer.py.
HIGHLIGHT_USE_QUEUE           = os.environ.get('HIGHLIGHT_USE_QUEUE', 'false').lower() == 'true'
RABBITMQ_URL                  = os.environ.get('RABBITMQ_URL', 'amqp://guest:guest@localhost:5673/')
RABBITMQ_HIGHLIGHT_QUEUE      = os.environ.get('RABBITMQ_HIGHLIGHT_QUEUE', 'highlight.detect')
RABBITMQ_HIGHLIGHT_EXCHANGE   = os.environ.get('RABBITMQ_HIGHLIGHT_EXCHANGE', 'highlight')
RABBITMQ_HIGHLIGHT_ROUTING_KEY = os.environ.get('RABBITMQ_HIGHLIGHT_ROUTING_KEY', 'highlight.results')
HIGHLIGHT_WORKER_TIMEOUT_SEC  = int(os.environ.get('HIGHLIGHT_WORKER_TIMEOUT_SEC', '900'))

# F09 — WebSocket via Django Channels (InMemoryChannelLayer para Fase 0)
ASGI_APPLICATION = 'config.asgi.application'
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'
