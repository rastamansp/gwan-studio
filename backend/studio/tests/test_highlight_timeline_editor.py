"""
F18 — editor de timeline de cortes: persistência do EDL (HighlightClipModel),
tela do editor, validação e recorte via /highlights/editor/save/.
"""
import json
import os
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from studio.models import HighlightClipModel, HighlightMomentModel, JobModel, ProjectModel, SourceModel


def _write_dummy_video(project_id: str, source_id: str) -> str:
    from infrastructure.storage import get_storage
    storage = get_storage()
    key = f'studio/{project_id}/sources/{source_id}.mp4'
    path = storage.resolve_write_path(key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(b'\x00' * 64)
    storage.finalize_write(key, path, 'video/mp4')
    return key


class HighlightClipPersistenceTests(TestCase):
    """Verifica que rodar highlight-detect (simulado) persiste HighlightClipModel."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username='coach', password='x')
        self.project = ProjectModel.objects.create(
            name='Jogo', owner=self.user, project_type=ProjectModel.ProjectType.FUTEBOL,
        )
        storage_key = _write_dummy_video(str(self.project.id), 'src1')
        self.source = SourceModel.objects.create(
            project=self.project, original_filename='1t.mp4', duration_sec=600,
            status=SourceModel.Status.READY, storage_key=storage_key,
        )
        self.job = JobModel.objects.create(
            project=self.project, job_type=JobModel.JobType.HIGHLIGHT_DETECT, status=JobModel.Status.PENDING,
        )

    @override_settings(HIGHLIGHT_SIMULATE=True)
    def test_clips_are_persisted_after_detection(self):
        from presentation.views.projects import _run_highlight_job

        _run_highlight_job(
            str(self.job.id), str(self.project.id), self.project.name,
            [self.source.storage_key], {
                'pre_roll': 6.0, 'post_roll': 8.0, 'merge_gap': 4.0,
                'top_n_peaks': 10, 'importancia_min': 5,
            },
        )
        clips = HighlightClipModel.objects.filter(project=self.project)
        self.assertGreater(clips.count(), 0)
        for clip in clips:
            self.assertEqual(clip.source_id, self.source.id)
            self.assertLess(clip.start_sec, clip.end_sec)
            self.assertTrue(clip.included)

    @override_settings(HIGHLIGHT_SIMULATE=True)
    def test_reprocessing_replaces_previous_clips(self):
        from presentation.views.projects import _run_highlight_job

        _run_highlight_job(
            str(self.job.id), str(self.project.id), self.project.name,
            [self.source.storage_key], {'top_n_peaks': 10, 'importancia_min': 5},
        )
        first_ids = set(HighlightClipModel.objects.filter(project=self.project).values_list('id', flat=True))

        job2 = JobModel.objects.create(
            project=self.project, job_type=JobModel.JobType.HIGHLIGHT_DETECT, status=JobModel.Status.PENDING,
        )
        _run_highlight_job(
            str(job2.id), str(self.project.id), self.project.name,
            [self.source.storage_key], {'top_n_peaks': 10, 'importancia_min': 5},
        )
        second_ids = set(HighlightClipModel.objects.filter(project=self.project).values_list('id', flat=True))
        self.assertTrue(first_ids.isdisjoint(second_ids))


@override_settings(HIGHLIGHT_SIMULATE=True)
class HighlightsEditorViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='coach', password='x')
        self.client.force_login(self.user)
        self.project = ProjectModel.objects.create(
            name='Jogo', owner=self.user, project_type=ProjectModel.ProjectType.FUTEBOL,
        )
        storage_key = _write_dummy_video(str(self.project.id), 'src1')
        self.source = SourceModel.objects.create(
            project=self.project, original_filename='1t.mp4', duration_sec=600,
            status=SourceModel.Status.READY, storage_key=storage_key,
        )
        self.clip = HighlightClipModel.objects.create(
            project=self.project, source=self.source, start_sec=10.0, end_sec=20.0, order=0, included=True,
        )

    def test_404_for_gopro_project(self):
        gopro = ProjectModel.objects.create(name='Pedalada', owner=self.user, project_type='gopro')
        resp = self.client.get(f'/projects/{gopro.id}/highlights/editor/')
        self.assertEqual(resp.status_code, 404)

    def test_renders_clip_data(self):
        resp = self.client.get(f'/projects/{self.project.id}/highlights/editor/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '1t.mp4')
        self.assertContains(resp, str(self.clip.id))

    def test_source_preview_streams_inline(self):
        resp = self.client.get(f'/projects/{self.project.id}/sources/{self.source.id}/preview/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('attachment', resp.get('Content-Disposition', ''))

    def test_source_preview_404_unknown_source(self):
        resp = self.client.get(f'/projects/{self.project.id}/sources/{uuid.uuid4()}/preview/')
        self.assertEqual(resp.status_code, 404)


@override_settings(HIGHLIGHT_SIMULATE=True)
class HighlightsEditorSaveTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='coach', password='x')
        self.client.force_login(self.user)
        self.project = ProjectModel.objects.create(
            name='Jogo', owner=self.user, project_type=ProjectModel.ProjectType.FUTEBOL,
        )
        storage_key = _write_dummy_video(str(self.project.id), 'src1')
        self.source = SourceModel.objects.create(
            project=self.project, original_filename='1t.mp4', duration_sec=100,
            status=SourceModel.Status.READY, storage_key=storage_key,
        )
        self.clip_a = HighlightClipModel.objects.create(
            project=self.project, source=self.source, start_sec=10.0, end_sec=20.0, order=0, included=True,
        )
        self.clip_b = HighlightClipModel.objects.create(
            project=self.project, source=self.source, start_sec=30.0, end_sec=40.0, order=1, included=True,
        )

    def _save(self, clips):
        return self.client.post(
            f'/projects/{self.project.id}/highlights/editor/save/',
            data=json.dumps({'clips': clips}),
            content_type='application/json',
        )

    def test_extends_clip_end_and_recuts(self):
        resp = self._save([
            {'id': str(self.clip_a.id), 'start_sec': 10.0, 'end_sec': 25.0, 'included': True},
            {'id': str(self.clip_b.id), 'start_sec': 30.0, 'end_sec': 40.0, 'included': True},
        ])
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['result']['num_clips'], 2)
        self.clip_a.refresh_from_db()
        self.assertEqual(self.clip_a.end_sec, 25.0)

    def test_rejects_overlapping_clips(self):
        resp = self._save([
            {'id': str(self.clip_a.id), 'start_sec': 10.0, 'end_sec': 35.0, 'included': True},
            {'id': str(self.clip_b.id), 'start_sec': 30.0, 'end_sec': 40.0, 'included': True},
        ])
        self.assertEqual(resp.status_code, 400)
        self.assertIn('sobrepostos', resp.json()['error'])
        self.clip_a.refresh_from_db()
        self.assertEqual(self.clip_a.end_sec, 20.0)  # nada foi persistido

    def test_rejects_out_of_bounds(self):
        resp = self._save([
            {'id': str(self.clip_a.id), 'start_sec': -5.0, 'end_sec': 20.0, 'included': True},
        ])
        self.assertEqual(resp.status_code, 400)

    def test_rejects_too_short_clip(self):
        resp = self._save([
            {'id': str(self.clip_a.id), 'start_sec': 10.0, 'end_sec': 10.2, 'included': True},
        ])
        self.assertEqual(resp.status_code, 400)

    def test_404_for_unknown_clip_id(self):
        resp = self._save([{'id': str(uuid.uuid4()), 'start_sec': 0, 'end_sec': 5, 'included': True}])
        self.assertEqual(resp.status_code, 404)

    def test_excluded_clip_is_not_checked_for_overlap(self):
        resp = self._save([
            {'id': str(self.clip_a.id), 'start_sec': 10.0, 'end_sec': 35.0, 'included': False},
            {'id': str(self.clip_b.id), 'start_sec': 30.0, 'end_sec': 40.0, 'included': True},
        ])
        self.assertEqual(resp.status_code, 200)

    def test_removes_included_moment_via_toggle_does_not_affect_clips(self):
        HighlightMomentModel.objects.create(
            project=self.project, source=self.source, timestamp_sec=15.0,
            tipo='gol', descricao='Gol', importancia=9, included=True,
        )
        resp = self._save([
            {'id': str(self.clip_a.id), 'start_sec': 10.0, 'end_sec': 20.0, 'included': True},
            {'id': str(self.clip_b.id), 'start_sec': 30.0, 'end_sec': 40.0, 'included': True},
        ])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(HighlightMomentModel.objects.filter(project=self.project).count(), 1)
