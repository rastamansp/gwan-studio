"""
F17 — teste de integração do pipeline de highlights em modo simulado
(sem FFmpeg/librosa/Claude reais). Cobre RF02-RF07 e o isolamento por
source (RN-F17 / REQ-F17-08).
"""
import os
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from studio.models import HighlightMomentModel, JobModel, ProjectModel, SourceModel


@override_settings(HIGHLIGHT_SIMULATE=True)
class HighlightPipelineTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='coach', password='x')
        self.project = ProjectModel.objects.create(
            name='Flamengo 2x1 Vasco',
            owner=self.user,
            project_type=ProjectModel.ProjectType.FUTEBOL,
            highlight_settings={
                'pre_roll': 6.0, 'post_roll': 8.0, 'merge_gap': 4.0,
                'top_n_peaks': 10, 'importancia_min': 5,
            },
        )

        media_dir = os.path.join(os.environ.get('TMP', '/tmp'), 'gwan_studio_test_media')
        os.makedirs(media_dir, exist_ok=True)
        video_path = os.path.join(media_dir, f'{uuid.uuid4()}.mp4')
        open(video_path, 'wb').close()

        self.source = SourceModel.objects.create(
            project=self.project,
            original_filename='primeiro_tempo.mp4',
            duration_sec=2700,
            status=SourceModel.Status.READY,
            storage_key=video_path,  # storage local: resolve_read_path retorna a própria key
        )

        self.job = JobModel.objects.create(
            project=self.project,
            job_type=JobModel.JobType.HIGHLIGHT_DETECT,
            status=JobModel.Status.PENDING,
        )

    def test_detects_moments_and_marks_project_highlights_done(self):
        from presentation.views.projects import _run_highlight_job

        _run_highlight_job(
            str(self.job.id), str(self.project.id), self.project.name,
            [self.source.storage_key], self.project.highlight_settings,
        )

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'done')

        self.project.refresh_from_db()
        self.assertEqual(self.project.phase, 'highlights_done')

        moments = HighlightMomentModel.objects.filter(project=self.project)
        self.assertGreater(moments.count(), 0)
        self.assertTrue(all(m.source_id == self.source.id for m in moments))

    def test_failing_source_does_not_crash_other_sources(self):
        """Uma storage_key sem SourceModel correspondente (RN de isolamento) não
        deve impedir a detecção nos demais sources válidos do mesmo job."""
        from presentation.views.projects import _run_highlight_job

        missing_key = '/path/que/nao/existe.mp4'  # sem SourceModel — get() falha

        _run_highlight_job(
            str(self.job.id), str(self.project.id), self.project.name,
            [missing_key, self.source.storage_key], self.project.highlight_settings,
        )

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'done')
        self.assertIn('[ERRO]', ' '.join(entry['text'] for entry in self.job.logs))
        self.assertGreater(HighlightMomentModel.objects.filter(project=self.project).count(), 0)
