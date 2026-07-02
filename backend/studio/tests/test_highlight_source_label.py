"""
F17 — indicador de fonte (`source_label`) na lista de momentos, útil quando
o projeto tem múltiplos vídeos (ex.: 1º/2º tempo).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from presentation.views.projects import _list_highlight_moments
from studio.models import HighlightMomentModel, ProjectModel, SourceModel


class HighlightSourceLabelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='coach', password='x')
        self.project = ProjectModel.objects.create(
            name='Jogo', owner=self.user, project_type=ProjectModel.ProjectType.FUTEBOL,
        )

    def test_no_label_with_single_source(self):
        source = SourceModel.objects.create(
            project=self.project, original_filename='jogo_completo.mp4',
            status=SourceModel.Status.READY, storage_key='a.mp4',
        )
        HighlightMomentModel.objects.create(
            project=self.project, source=source, timestamp_sec=10.0,
            tipo='gol', descricao='Gol', importancia=9, included=True,
        )
        moments = _list_highlight_moments(str(self.project.id))
        self.assertIsNone(moments[0]['source_label'])

    def test_label_shows_ordinal_and_filename_with_multiple_sources(self):
        first_half = SourceModel.objects.create(
            project=self.project, original_filename='1t.mp4', sort_order=0,
            status=SourceModel.Status.READY, storage_key='1t.mp4',
        )
        second_half = SourceModel.objects.create(
            project=self.project, original_filename='2t.mp4', sort_order=1,
            status=SourceModel.Status.READY, storage_key='2t.mp4',
        )
        HighlightMomentModel.objects.create(
            project=self.project, source=first_half, timestamp_sec=10.0,
            tipo='gol', descricao='Gol no 1T', importancia=9, included=True,
        )
        HighlightMomentModel.objects.create(
            project=self.project, source=second_half, timestamp_sec=20.0,
            tipo='gol', descricao='Gol no 2T', importancia=9, included=True,
        )
        moments = {m['descricao']: m for m in _list_highlight_moments(str(self.project.id))}
        self.assertEqual(moments['Gol no 1T']['source_label'], '1º tempo — 1t.mp4')
        self.assertEqual(moments['Gol no 2T']['source_label'], '2º tempo — 2t.mp4')

    def test_no_label_when_source_is_null(self):
        HighlightMomentModel.objects.create(
            project=self.project, source=None, timestamp_sec=10.0,
            tipo='gol', descricao='Gol', importancia=9, included=True,
        )
        moments = _list_highlight_moments(str(self.project.id))
        self.assertIsNone(moments[0]['source_label'])
