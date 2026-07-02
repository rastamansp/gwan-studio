"""
F07 — Upload de vídeo para YouTube via Data API v3.
"""
from django.conf import settings
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']


def upload_video(
    refresh_token_enc: str,
    video_path: str,
    title: str,
    description: str,
    tags: list,
    visibility: str,
    log_fn=None,
) -> str:
    """
    Faz upload do vídeo para o YouTube e retorna o video_id.
    refresh_token_enc: refresh token (plain em dev, Fernet-enc em prod).
    """
    if log_fn is None:
        log_fn = lambda _: None

    refresh_token = _decode_token(refresh_token_enc)

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )
    creds.refresh(Request())

    youtube = build('youtube', 'v3', credentials=creds, cache_discovery=False)

    log_fn('Iniciando upload para YouTube…')
    media = MediaFileUpload(video_path, chunksize=1024 * 1024, resumable=True)
    insert_request = youtube.videos().insert(
        part='snippet,status',
        body={
            'snippet': {
                'title':       title or 'Vídeo sem título',
                'description': description or '',
                'tags':        tags or [],
                'categoryId':  '22',  # People & Blogs
            },
            'status': {
                'privacyStatus': visibility,
            },
        },
        media_body=media,
    )

    response = None
    while response is None:
        status, response = insert_request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            log_fn(f'Upload {pct}%…')

    video_id = response['id']
    log_fn(f'Upload concluído — video_id: {video_id}')
    return video_id


def _decode_token(token_enc: str) -> str:
    """Plain em dev (sem OAUTH_ENCRYPTION_KEY); Fernet em prod."""
    encryption_key = getattr(settings, 'OAUTH_ENCRYPTION_KEY', '')
    if not encryption_key:
        return token_enc
    from cryptography.fernet import Fernet
    f = Fernet(encryption_key.encode())
    return f.decrypt(token_enc.encode()).decode()
