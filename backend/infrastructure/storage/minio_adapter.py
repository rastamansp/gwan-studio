"""MinioStorageAdapter — artefatos no MinIO via boto3 (S3-compatible)."""
import hashlib
import os
from pathlib import Path

from domain.ports import IObjectStoragePort


def _cache_filename(key: str) -> str:
    """Nome de arquivo local curto e determinístico para uma S3 key.

    Necessário no Windows: uma key como `studio/<uuid>/sources/<uuid>-<nome
    original longo>.mp4` combinada com o `media_root` do projeto facilmente
    estoura o limite de 260 caracteres do MAX_PATH clássico, e o download via
    boto3/s3transfer falha com `FileNotFoundError` ao abrir o arquivo
    temporário. O cache é só uso interno (nunca exposto), então achatar em
    hash + extensão remove o problema sem afetar a key real no bucket.
    """
    ext = Path(key).suffix
    digest = hashlib.sha256(key.encode('utf-8')).hexdigest()
    return f'{digest}{ext}'


class MinioStorageAdapter(IObjectStoragePort):
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        media_root: str,
    ):
        import boto3
        from botocore.config import Config
        self._bucket = bucket
        self._s3 = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version='s3v4'),
            region_name='us-east-1',
        )
        self._cache = Path(media_root) / '_minio_cache'
        self._temp  = Path(media_root) / '_minio_temp'
        self._cache.mkdir(parents=True, exist_ok=True)
        self._temp.mkdir(parents=True, exist_ok=True)

    @property
    def is_local(self) -> bool:
        return False

    def put_object(self, key: str, data: bytes, content_type: str) -> None:
        import io
        self._s3.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=io.BytesIO(data),
            ContentType=content_type,
        )

    def resolve_read_path(self, key: str) -> str:
        target = self._cache / _cache_filename(key)
        if not target.exists():
            self._s3.download_file(self._bucket, key, str(target))
        return str(target)

    def resolve_write_path(self, key: str) -> str:
        path = self._temp / _cache_filename(key)
        return str(path)

    def finalize_write(self, key: str, local_path: str, content_type: str) -> None:
        self._s3.upload_file(
            local_path,
            self._bucket,
            key,
            ExtraArgs={'ContentType': content_type},
        )

    def object_exists(self, key: str) -> bool:
        try:
            self._s3.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    def get_presigned_url(self, key: str, expires: int = 3600) -> str:
        return self._s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': self._bucket, 'Key': key},
            ExpiresIn=expires,
        )

    def delete_object(self, key: str) -> None:
        self._s3.delete_object(Bucket=self._bucket, Key=key)
