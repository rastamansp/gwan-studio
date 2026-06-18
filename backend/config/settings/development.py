from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# Em dev, usa staticfiles storage simples (sem hash de arquivo)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
