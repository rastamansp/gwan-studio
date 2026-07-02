"""
Item 6 — testes de integração HTTP do fluxo completo do pipeline "Futebol":
criação do projeto → upload → highlights → export → thumbnails → SEO,
exercitando as URLs reais (não chamando funções internas diretamente).

Os jobs (`highlight_detect`, `export`, `thumbnail`, `seo`) rodam em threads
daemon disparadas pelas views. Para tornar o teste determinístico sem
depender de polling/sleep, `threading.Thread` é substituído por uma versão
síncrona (`start()` chama o target na hora) só dentro deste módulo de teste —
o código de produção continua assíncrono de verdade.
"""
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from studio.models import HighlightMomentModel, JobModel, ProjectModel, SourceModel


class SyncThread:
    """Substitui threading.Thread nos testes: start() roda o target na hora."""
    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


def _fake_video_upload(name='clip.mp4'):
    return BytesIO(b'\x00\x00\x00\x18ftypmp42' + b'\x00' * 256), name


@override_settings(
    HIGHLIGHT_SIMULATE=True, MERGE_SIMULATE=True,
    EXPORT_SIMULATE=True, THUMBNAIL_SIMULATE=True, SEO_SIMULATE=True,
)
@patch('presentation.views.projects.threading.Thread', SyncThread)
class FutebolFullJourneyHttpTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='coach', password='x')
        self.client.force_login(self.user)

    def _create_futebol_project(self) -> str:
        resp = self.client.post('/projects/new/', data={
            'name': 'Final da Copa', 'channel_name': '@meucanal', 'project_type': 'futebol',
        })
        self.assertEqual(resp.status_code, 302)
        project_id = resp.url.strip('/').split('/')[-1]
        self.assertTrue(ProjectModel.objects.filter(id=project_id, project_type='futebol').exists())
        return project_id

    def _upload_source(self, project_id: str, filename='1t.mp4'):
        from django.core.files.uploadedfile import SimpleUploadedFile

        data, name = _fake_video_upload(filename)
        upload = SimpleUploadedFile(name, data.getvalue(), content_type='video/mp4')
        resp = self.client.post(f'/projects/{project_id}/sources/upload/', data={'file': upload})
        self.assertEqual(resp.status_code, 200)

    def test_full_journey_gopro_vs_futebol_uses_different_steps(self):
        """REQ-F01-07/F17: o wizard cria o project_type certo e a etapa 2 do
        pipeline muda de 'Merge' para 'Highlights' de acordo com o tipo."""
        futebol_id = self._create_futebol_project()

        resp = self.client.post('/projects/new/', data={
            'name': 'Pedalada', 'channel_name': '', 'project_type': 'gopro',
        })
        gopro_id = resp.url.strip('/').split('/')[-1]

        resp = self.client.get(f'/projects/{futebol_id}/')
        self.assertContains(resp, 'Highlights')
        self.assertNotContains(resp, f'/projects/{futebol_id}/merge/')

        resp = self.client.get(f'/projects/{gopro_id}/')
        self.assertContains(resp, f'/projects/{gopro_id}/merge/')
        self.assertNotContains(resp, f'/projects/{gopro_id}/highlights/')

    def test_full_pipeline_end_to_end_via_http(self):
        project_id = self._create_futebol_project()
        self._upload_source(project_id, '1t.mp4')
        self._upload_source(project_id, '2t.mp4')

        # ── Highlights ──────────────────────────────────────────
        resp = self.client.post(f'/projects/{project_id}/highlights/start/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            JobModel.objects.get(project_id=project_id, job_type='highlight_detect').status, 'done',
        )
        moments = list(HighlightMomentModel.objects.filter(project_id=project_id))
        self.assertGreater(len(moments), 0)

        resp = self.client.get(f'/projects/{project_id}/highlights/')
        self.assertContains(resp, 'Highlights Detectados')

        # Revisão manual — exclui um momento (REQ-F17-06)
        moment = moments[0]
        resp = self.client.post(f'/projects/{project_id}/highlights/{moment.id}/toggle/')
        self.assertEqual(resp.status_code, 200)
        moment.refresh_from_db()
        self.assertFalse(moment.included)

        # ── Export ──────────────────────────────────────────────
        resp = self.client.post(f'/projects/{project_id}/export/start/', data={'codec': 'copy'})
        self.assertEqual(resp.status_code, 200)
        export_job = JobModel.objects.get(project_id=project_id, job_type='export')
        self.assertEqual(export_job.status, 'done')

        project = ProjectModel.objects.get(id=project_id)
        self.assertEqual(project.phase, 'export_done')

        # RN-F17-04 — highlights bloqueados após o export, via HTTP real.
        resp = self.client.post(f'/projects/{project_id}/highlights/start/')
        self.assertContains(resp, 'exportados')
        self.assertEqual(
            JobModel.objects.filter(project_id=project_id, job_type='highlight_detect').count(), 1,
        )

        # ── Thumbnails ──────────────────────────────────────────
        resp = self.client.post(f'/projects/{project_id}/thumbnail/generate/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            JobModel.objects.get(project_id=project_id, job_type='thumbnail').status, 'done',
        )
        resp = self.client.get(f'/projects/{project_id}/thumbnail/')
        self.assertContains(resp, 'Thumbnails')

        # ── SEO ─────────────────────────────────────────────────
        resp = self.client.post(f'/projects/{project_id}/seo/generate/', data={'context': 'Final da Copa'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(JobModel.objects.get(project_id=project_id, job_type='seo').status, 'done')

        project.refresh_from_db()
        self.assertEqual(project.phase, 'thumbnails_done')

    def test_highlight_detect_requires_at_least_one_ready_source(self):
        project_id = self._create_futebol_project()
        resp = self.client.post(f'/projects/{project_id}/highlights/start/')
        self.assertContains(resp, 'Adicione pelo menos uma fonte')
        self.assertFalse(
            JobModel.objects.filter(project_id=project_id, job_type='highlight_detect').exists(),
        )


class ProjectOwnershipAndAuthTests(TestCase):
    def test_anonymous_user_is_redirected_to_login(self):
        resp = self.client.get('/dashboard/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp.url)

    def test_cannot_access_another_users_project(self):
        owner = get_user_model().objects.create_user(username='owner', password='x')
        intruder = get_user_model().objects.create_user(username='intruder', password='x')
        project = ProjectModel.objects.create(name='Privado', owner=owner, project_type='futebol')

        self.client.force_login(intruder)
        resp = self.client.get(f'/projects/{project.id}/')
        self.assertEqual(resp.status_code, 404)

        resp = self.client.get(f'/api/projects/{project.id}/highlights/')
        self.assertEqual(resp.status_code, 404)
