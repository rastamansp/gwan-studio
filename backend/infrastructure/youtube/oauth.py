"""
Utilitários OAuth YouTube — encode/decode de tokens.
"""
from django.conf import settings
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']


def encode_token(token: str) -> str:
    """Plain em dev (sem OAUTH_ENCRYPTION_KEY); Fernet em prod."""
    encryption_key = getattr(settings, 'OAUTH_ENCRYPTION_KEY', '')
    if not encryption_key:
        return token
    try:
        from cryptography.fernet import Fernet
        f = Fernet(encryption_key.encode())
        return f.encrypt(token.encode()).decode()
    except Exception:
        # Chave inválida (ex.: hex no .env) — fallback plain text em dev local
        return token


def get_credentials(refresh_token: str) -> Credentials:
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds
