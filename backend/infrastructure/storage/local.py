"""LocalStorageAdapter — armazena artefatos no filesystem (MEDIA_ROOT)."""
import os
import shutil
from pathlib import Path

from domain.ports import IObjectStoragePort


class LocalStorageAdapter(IObjectStoragePort):
    def __init__(self, media_root: str, media_url: str):
        self._root = Path(media_root)
        self._url = media_url.rstrip('/')

    @property
    def is_local(self) -> bool:
        return True

    def _abs(self, key: str) -> Path:
        return self._root / key

    def put_object(self, key: str, data: bytes, content_type: str) -> None:
        path = self._abs(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def resolve_read_path(self, key: str) -> str:
        return str(self._abs(key))

    def resolve_write_path(self, key: str) -> str:
        path = self._abs(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    def finalize_write(self, key: str, local_path: str, content_type: str) -> None:
        # Already on disk at the right place — nothing to do.
        target = str(self._abs(key))
        if os.path.normpath(local_path) != os.path.normpath(target):
            # Wrote to a different path — copy into place.
            Path(target).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local_path, target)

    def object_exists(self, key: str) -> bool:
        return self._abs(key).exists()

    def get_presigned_url(self, key: str, expires: int = 3600) -> str:
        # Local: return the media URL (no expiry enforcement).
        return f'{self._url}/{key}'

    def delete_object(self, key: str) -> None:
        p = self._abs(key)
        if p.exists():
            p.unlink()
