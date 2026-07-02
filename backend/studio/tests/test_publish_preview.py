"""
REQ-F07-09/10 — pré-visualização e download do final.mp4 na etapa Publicar.
"""
import os

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from studio.models import ProjectModel


class ExportPreviewViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='coach', password='x')
        self.client.force_login(self.user)
        self.project = ProjectModel.objects.create(name='Jogo', owner=self.user, project_type='gopro')

    def test_404_when_no_final_video(self):
        resp = self.client.get(f'/projects/{self.project.id}/export/preview/')
        self.assertEqual(resp.status_code, 404)

    def test_streams_inline_without_attachment_header(self):
        from infrastructure.storage import get_storage
        storage = get_storage()
        final_key = f'studio/{self.project.id}/final/final.mp4'
        path = storage.resolve_write_path(final_key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(b'\x00' * 100)
        storage.finalize_write(final_key, path, 'video/mp4')

        resp = self.client.get(f'/projects/{self.project.id}/export/preview/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('attachment', resp.get('Content-Disposition', ''))
        self.assertEqual(resp['Content-Type'], 'video/mp4')

    def test_download_forces_attachment(self):
        from infrastructure.storage import get_storage
        storage = get_storage()
        final_key = f'studio/{self.project.id}/final/final.mp4'
        path = storage.resolve_write_path(final_key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(b'\x00' * 100)
        storage.finalize_write(final_key, path, 'video/mp4')

        resp = self.client.get(f'/projects/{self.project.id}/export/download/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('attachment', resp.get('Content-Disposition', ''))
        self.assertIn('final.mp4', resp.get('Content-Disposition', ''))


class PublishStepVideoAvailableTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='coach', password='x')
        self.client.force_login(self.user)
        self.project = ProjectModel.objects.create(name='Jogo', owner=self.user, project_type='gopro')

    def test_publish_page_hides_preview_without_export(self):
        resp = self.client.get(f'/projects/{self.project.id}/publish/')
        self.assertFalse(resp.context['video_available'])
        self.assertNotContains(resp, 'export/preview/')

    def test_publish_page_shows_preview_after_export(self):
        from infrastructure.storage import get_storage
        storage = get_storage()
        final_key = f'studio/{self.project.id}/final/final.mp4'
        path = storage.resolve_write_path(final_key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(b'\x00' * 100)
        storage.finalize_write(final_key, path, 'video/mp4')

        resp = self.client.get(f'/projects/{self.project.id}/publish/')
        self.assertTrue(resp.context['video_available'])
        self.assertContains(resp, 'export/preview/')
        self.assertContains(resp, 'export/download/')
