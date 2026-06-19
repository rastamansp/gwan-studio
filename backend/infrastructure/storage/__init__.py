"""Factory para o IObjectStoragePort — retorna adaptador conforme STORAGE_BACKEND."""
import threading

from domain.ports import IObjectStoragePort

_instance: IObjectStoragePort | None = None
_lock = threading.Lock()


def get_storage() -> IObjectStoragePort:
    global _instance
    if _instance is not None:
        return _instance
    with _lock:
        if _instance is None:
            _instance = _build()
        return _instance


def _build() -> IObjectStoragePort:
    from django.conf import settings
    backend = getattr(settings, 'STORAGE_BACKEND', 'local')
    media_root = str(settings.MEDIA_ROOT)
    media_url  = settings.MEDIA_URL

    if backend == 'minio':
        from .minio_adapter import MinioStorageAdapter
        return MinioStorageAdapter(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            bucket=getattr(settings, 'MINIO_BUCKET', 'studio'),
            media_root=media_root,
        )

    from .local import LocalStorageAdapter
    return LocalStorageAdapter(media_root=media_root, media_url=media_url)
