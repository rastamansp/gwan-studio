"""
Import de source a partir de um link do YouTube (alternativa ao upload de
arquivo) — validação de URL, fluxo assíncrono e persistência do Source.
"""
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from infrastructure.youtube.downloader import is_youtube_url
from studio.models import ProjectModel, SourceModel


class SyncThread:
    """threading.Thread síncrono para os testes (mesma razão dos outros
    arquivos de teste: TestCase roda em transação não commitada)."""
    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


class IsYoutubeUrlTests(TestCase):
    def test_accepts_watch_url(self):
        self.assertTrue(is_youtube_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ'))

    def test_accepts_short_url(self):
        self.assertTrue(is_youtube_url('https://youtu.be/dQw4w9WgXcQ'))

    def test_accepts_shorts_url(self):
        self.assertTrue(is_youtube_url('https://www.youtube.com/shorts/dQw4w9WgXcQ'))

    def test_accepts_without_scheme(self):
        self.assertTrue(is_youtube_url('youtube.com/watch?v=dQw4w9WgXcQ'))

    def test_rejects_other_domains(self):
        self.assertFalse(is_youtube_url('https://vimeo.com/12345'))
        self.assertFalse(is_youtube_url('https://example.com/watch?v=x'))

    def test_rejects_empty(self):
        self.assertFalse(is_youtube_url(''))
        self.assertFalse(is_youtube_url(None))


@patch('presentation.views.projects.threading.Thread', SyncThread)
class ImportSourceFromYoutubeViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='coach', password='x')
        self.client.force_login(self.user)
        self.project = ProjectModel.objects.create(name='Jogo', owner=self.user, project_type='futebol')

    def _post(self, url):
        return self.client.post(f'/projects/{self.project.id}/sources/from-youtube/', data={'url': url})

    def test_rejects_missing_url(self):
        resp = self._post('')
        self.assertEqual(resp.status_code, 400)

    def test_rejects_non_youtube_url(self):
        resp = self._post('https://vimeo.com/12345')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('YouTube', resp.json()['error'])

    @patch('infrastructure.youtube.downloader.download_youtube_video')
    def test_creates_source_and_marks_ready_on_success(self, mock_download):
        def fake_download(url, output_path_no_ext):
            path = output_path_no_ext + '.mp4'
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as f:
                f.write(b'\x00' * 512)
            return {'title': 'meu_video.mp4', 'duration_sec': 245, 'filepath': path}

        mock_download.side_effect = fake_download

        resp = self._post('https://youtu.be/dQw4w9WgXcQ')
        self.assertEqual(resp.status_code, 202)
        source_id = resp.json()['id']

        source = SourceModel.objects.get(id=source_id)
        self.assertEqual(source.status, 'ready')
        self.assertEqual(source.duration_sec, 245)
        self.assertEqual(source.size_bytes, 512)
        self.assertTrue(source.storage_key)

        self.project.refresh_from_db()
        self.assertEqual(self.project.phase, 'sources_uploaded')

    @patch('infrastructure.youtube.downloader.download_youtube_video')
    def test_marks_source_as_error_on_download_failure(self, mock_download):
        from infrastructure.youtube.downloader import YouTubeDownloadError
        mock_download.side_effect = YouTubeDownloadError('Video indisponível')

        resp = self._post('https://youtu.be/dQw4w9WgXcQ')
        self.assertEqual(resp.status_code, 202)
        source_id = resp.json()['id']

        source = SourceModel.objects.get(id=source_id)
        self.assertEqual(source.status, 'error')
        self.assertIn('Video indisponível', source.original_filename)
