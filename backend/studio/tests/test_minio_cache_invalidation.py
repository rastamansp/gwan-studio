"""
Regressão: MinioStorageAdapter.finalize_write() precisa atualizar o cache
local de leitura — sem isso, recortar o merged.mp4 de novo (F18) serviria a
versão antiga em resolve_read_path() até o processo reiniciar.

Requer um MinIO real (docker-compose.dev.yml, http://localhost:9018). Pulado
automaticamente se não estiver no ar.
"""
import uuid

from django.test import SimpleTestCase

MINIO_ENDPOINT = 'http://localhost:9018'
MINIO_ACCESS_KEY = 'minioadmin'
MINIO_SECRET_KEY = 'minioadmin'
MINIO_BUCKET = 'studio'


def _minio_available() -> bool:
    try:
        import boto3
        from botocore.config import Config
        client = boto3.client(
            's3', endpoint_url=MINIO_ENDPOINT,
            aws_access_key_id=MINIO_ACCESS_KEY, aws_secret_access_key=MINIO_SECRET_KEY,
            config=Config(signature_version='s3v4'), region_name='us-east-1',
        )
        client.list_buckets()
        return True
    except Exception:
        return False


class MinioCacheInvalidationTests(SimpleTestCase):
    def setUp(self):
        if not _minio_available():
            self.skipTest(
                f'MinIO não disponível em {MINIO_ENDPOINT} — suba '
                '`docker compose -f gwan-studio/docker-compose.dev.yml up -d` para rodar este teste.'
            )

    def test_resolve_read_path_reflects_latest_finalize_write(self):
        import tempfile

        from infrastructure.storage.minio_adapter import MinioStorageAdapter

        with tempfile.TemporaryDirectory() as media_root:
            storage = MinioStorageAdapter(
                endpoint=MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY,
                bucket=MINIO_BUCKET, media_root=media_root,
            )
            key = f'studio/test-cache-invalidation/{uuid.uuid4().hex}.mp4'
            try:
                # 1ª versão
                path_v1 = storage.resolve_write_path(key)
                with open(path_v1, 'wb') as f:
                    f.write(b'VERSAO-1')
                storage.finalize_write(key, path_v1, 'video/mp4')

                read_path = storage.resolve_read_path(key)
                with open(read_path, 'rb') as f:
                    self.assertEqual(f.read(), b'VERSAO-1')

                # 2ª versão — mesma key, conteúdo diferente (simula recorte de novo)
                path_v2 = storage.resolve_write_path(key)
                with open(path_v2, 'wb') as f:
                    f.write(b'VERSAO-2-MAIOR-QUE-A-PRIMEIRA')
                storage.finalize_write(key, path_v2, 'video/mp4')

                # resolve_read_path não deve servir o cache antigo (VERSAO-1).
                read_path_2 = storage.resolve_read_path(key)
                with open(read_path_2, 'rb') as f:
                    self.assertEqual(f.read(), b'VERSAO-2-MAIOR-QUE-A-PRIMEIRA')
            finally:
                storage.delete_object(key)
