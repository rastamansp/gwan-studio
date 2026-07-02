"""
F17 — RN-F17-04: highlight-detect não pode reprocessar depois que o projeto
já foi exportado (fases em EXPORTED_PHASES).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from presentation.views.projects import (
    EXPORTED_PHASES, HighlightDetectError, _launch_highlight_job, _project_is_exported,
)
from studio.models import HighlightMomentModel, JobModel, ProjectModel, SourceModel


class ProjectIsExportedTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='coach', password='x')

    def test_true_for_each_exported_phase(self):
        for phase in EXPORTED_PHASES:
            project = ProjectModel.objects.create(
                name='Jogo', owner=self.user,
                project_type=ProjectModel.ProjectType.FUTEBOL, phase=phase,
            )
            self.assertTrue(_project_is_exported(project), phase)

    def test_false_before_export(self):
        for phase in ('new', 'sources_uploaded', 'highlights_done'):
            project = ProjectModel.objects.create(
                name='Jogo', owner=self.user,
                project_type=ProjectModel.ProjectType.FUTEBOL, phase=phase,
            )
            self.assertFalse(_project_is_exported(project), phase)


class LaunchHighlightJobLockTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='coach', password='x')

    def test_raises_locked_error_after_export(self):
        project = ProjectModel.objects.create(
            name='Jogo', owner=self.user,
            project_type=ProjectModel.ProjectType.FUTEBOL, phase='export_done',
        )
        SourceModel.objects.create(
            project=project, original_filename='1t.mp4', duration_sec=2700,
            status=SourceModel.Status.READY, storage_key='dummy.mp4',
        )
        with self.assertRaises(HighlightDetectError) as ctx:
            _launch_highlight_job(project)
        self.assertEqual(ctx.exception.status, 409)
        self.assertEqual(ctx.exception.code, 'locked')
        # Nenhum job deve ter sido criado quando bloqueado.
        self.assertEqual(JobModel.objects.filter(project=project).count(), 0)

    @override_settings(HIGHLIGHT_SIMULATE=True)
    def test_allows_reprocessing_before_export(self):
        project = ProjectModel.objects.create(
            name='Jogo', owner=self.user,
            project_type=ProjectModel.ProjectType.FUTEBOL, phase='highlights_done',
        )
        SourceModel.objects.create(
            project=project, original_filename='1t.mp4', duration_sec=2700,
            status=SourceModel.Status.READY, storage_key='dummy.mp4',
        )
        job = _launch_highlight_job(project)
        self.assertEqual(job.status, 'pending')


@override_settings(HIGHLIGHT_SIMULATE=True)
class HighlightApiLockTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='coach', password='x')
        self.client.force_login(self.user)

    def test_api_returns_409_after_export(self):
        project = ProjectModel.objects.create(
            name='Jogo', owner=self.user,
            project_type=ProjectModel.ProjectType.FUTEBOL, phase='export_done',
        )
        SourceModel.objects.create(
            project=project, original_filename='1t.mp4', duration_sec=2700,
            status=SourceModel.Status.READY, storage_key='dummy.mp4',
        )
        resp = self.client.post(f'/api/projects/{project.id}/jobs/highlight-detect/')
        self.assertEqual(resp.status_code, 409)
        self.assertIn('exportados', resp.json()['detail'])


@override_settings(HIGHLIGHT_SIMULATE=True)
class HighlightsStartViewLockTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='coach', password='x')
        self.client.force_login(self.user)

    def test_htmx_start_shows_editor_with_lock_message(self):
        project = ProjectModel.objects.create(
            name='Jogo', owner=self.user,
            project_type=ProjectModel.ProjectType.FUTEBOL, phase='export_done',
        )
        SourceModel.objects.create(
            project=project, original_filename='1t.mp4', duration_sec=2700,
            status=SourceModel.Status.READY, storage_key='dummy.mp4',
        )
        resp = self.client.post(f'/projects/{project.id}/highlights/start/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('exportados', resp.content.decode('utf-8'))
        self.assertEqual(JobModel.objects.filter(project=project).count(), 0)

    def test_reprocess_query_param_forces_editor_even_with_existing_result(self):
        from presentation.views.projects import _highlight_template_and_ctx

        project = ProjectModel.objects.create(
            name='Jogo', owner=self.user,
            project_type=ProjectModel.ProjectType.FUTEBOL, phase='highlights_done',
        )
        HighlightMomentModel.objects.create(
            project=project, timestamp_sec=10.0, tipo='gol',
            descricao='Gol', importancia=9, included=True,
        )
        JobModel.objects.create(project=project, job_type='highlight_detect', status='done')

        template, _ctx = _highlight_template_and_ctx(str(project.id))
        self.assertEqual(template, 'highlights/_result.html')

        template, _ctx = _highlight_template_and_ctx(str(project.id), force_editor=True)
        self.assertEqual(template, 'highlights/_editor.html')
