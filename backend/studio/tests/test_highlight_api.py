"""
F17 — testes dos endpoints REST documentados em docs/spec/30-contracts/api-contracts.md:
  POST  /api/projects/:id/jobs/highlight-detect/
  GET   /api/projects/:id/highlights/
  PATCH /api/projects/:id/highlights/:highlightId/
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from studio.models import HighlightMomentModel, ProjectModel, SourceModel


class HighlightDetectApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='coach', password='x')
        self.client.force_login(self.user)

    def test_returns_409_for_gopro_project(self):
        project = ProjectModel.objects.create(
            name='Pedalada', owner=self.user, project_type=ProjectModel.ProjectType.GOPRO,
        )
        resp = self.client.post(f'/api/projects/{project.id}/jobs/highlight-detect/')
        self.assertEqual(resp.status_code, 409)

    def test_returns_400_when_no_ready_sources(self):
        project = ProjectModel.objects.create(
            name='Jogo', owner=self.user, project_type=ProjectModel.ProjectType.FUTEBOL,
        )
        resp = self.client.post(f'/api/projects/{project.id}/jobs/highlight-detect/')
        self.assertEqual(resp.status_code, 400)

    @override_settings(HIGHLIGHT_SIMULATE=True)
    def test_starts_job_and_returns_202(self):
        project = ProjectModel.objects.create(
            name='Jogo', owner=self.user, project_type=ProjectModel.ProjectType.FUTEBOL,
        )
        SourceModel.objects.create(
            project=project, original_filename='1t.mp4', duration_sec=2700,
            status=SourceModel.Status.READY, storage_key='dummy.mp4',
        )
        resp = self.client.post(f'/api/projects/{project.id}/jobs/highlight-detect/')
        self.assertEqual(resp.status_code, 202)
        data = resp.json()
        self.assertIn('job_id', data)
        self.assertEqual(data['status'], 'pending')

    def test_requires_post(self):
        project = ProjectModel.objects.create(
            name='Jogo', owner=self.user, project_type=ProjectModel.ProjectType.FUTEBOL,
        )
        resp = self.client.get(f'/api/projects/{project.id}/jobs/highlight-detect/')
        self.assertEqual(resp.status_code, 405)


class HighlightListApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='coach', password='x')
        self.client.force_login(self.user)
        self.project = ProjectModel.objects.create(
            name='Jogo', owner=self.user, project_type=ProjectModel.ProjectType.FUTEBOL,
        )

    def test_lists_moments_as_json(self):
        HighlightMomentModel.objects.create(
            project=self.project, timestamp_sec=1245.0, tipo='gol',
            descricao='Gol de cabeça', importancia=9, included=True,
        )
        resp = self.client.get(f'/api/projects/{self.project.id}/highlights/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['tipo'], 'gol')
        self.assertEqual(data[0]['importancia'], 9)
        self.assertTrue(data[0]['included'])

    def test_empty_project_returns_empty_list(self):
        resp = self.client.get(f'/api/projects/{self.project.id}/highlights/')
        self.assertEqual(resp.json(), [])


class HighlightUpdateApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='coach', password='x')
        self.client.force_login(self.user)
        self.project = ProjectModel.objects.create(
            name='Jogo', owner=self.user, project_type=ProjectModel.ProjectType.FUTEBOL,
        )
        self.moment = HighlightMomentModel.objects.create(
            project=self.project, timestamp_sec=100.0, tipo='chance',
            descricao='Quase gol', importancia=6, included=True,
        )

    def test_toggles_included_flag(self):
        resp = self.client.patch(
            f'/api/projects/{self.project.id}/highlights/{self.moment.id}/',
            data=json.dumps({'included': False}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['included'])
        self.moment.refresh_from_db()
        self.assertFalse(self.moment.included)

    def test_404_for_unknown_moment(self):
        resp = self.client.patch(
            f'/api/projects/{self.project.id}/highlights/00000000-0000-0000-0000-000000000000/',
            data=json.dumps({'included': False}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_400_for_invalid_json_body(self):
        resp = self.client.patch(
            f'/api/projects/{self.project.id}/highlights/{self.moment.id}/',
            data='not-json',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
