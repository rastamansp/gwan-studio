"""
Configurações base — compartilhadas entre development e production.
Não usar diretamente: usar development.py ou production.py.
"""
from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.staticfiles',
    'django.contrib.sessions',
    'django.contrib.messages',
    'channels',
    'rest_framework',
    'django_htmx',
    'django_celery_results',
    'studio',  # app local com os models (ProjectModel etc.)
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
ASGI_APPLICATION = 'config.asgi.application'

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

# Database
import dj_database_url  # noqa — adicionado em requirements
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Redis / Celery
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379/0')

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = 'django-db'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {'hosts': [REDIS_URL]},
    }
}

# Static
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# MinIO
STORAGE_BACKEND = config('STORAGE_BACKEND', default='minio')
MINIO_ENDPOINT = config('MINIO_ENDPOINT', default='localhost:9000')
MINIO_ACCESS_KEY = config('MINIO_ACCESS_KEY', default='minioadmin')
MINIO_SECRET_KEY = config('MINIO_SECRET_KEY', default='minioadmin')
MINIO_BUCKET = config('MINIO_BUCKET', default='studio')
MINIO_USE_SSL = config('MINIO_USE_SSL', default=False, cast=bool)

# F17 — ponte RabbitMQ com o highlight-worker externo (Whisper + Claude reais).
HIGHLIGHT_USE_QUEUE = config('HIGHLIGHT_USE_QUEUE', default=False, cast=bool)
RABBITMQ_URL = config('RABBITMQ_URL', default='amqp://guest:guest@localhost:5672/')
RABBITMQ_HIGHLIGHT_QUEUE = config('RABBITMQ_HIGHLIGHT_QUEUE', default='highlight.detect')
RABBITMQ_HIGHLIGHT_EXCHANGE = config('RABBITMQ_HIGHLIGHT_EXCHANGE', default='highlight')
RABBITMQ_HIGHLIGHT_ROUTING_KEY = config('RABBITMQ_HIGHLIGHT_ROUTING_KEY', default='highlight.results')
HIGHLIGHT_WORKER_TIMEOUT_SEC = config('HIGHLIGHT_WORKER_TIMEOUT_SEC', default=900, cast=int)

# IA
ANTHROPIC_API_KEY = config('ANTHROPIC_API_KEY', default='')

# YouTube OAuth
GOOGLE_CLIENT_ID = config('GOOGLE_CLIENT_ID', default='')
GOOGLE_CLIENT_SECRET = config('GOOGLE_CLIENT_SECRET', default='')
OAUTH_REDIRECT_URI = config('OAUTH_REDIRECT_URI', default='http://localhost:3018/api/oauth/youtube/callback/')
OAUTH_ENCRYPTION_KEY = config('OAUTH_ENCRYPTION_KEY', default='')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'
