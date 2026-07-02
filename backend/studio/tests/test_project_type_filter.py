"""
REQ-F01 — filtro de listagem de projetos por `project_type` (dashboard/lista).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from application.projects.use_cases import ListProjects
from infrastructure.orm.repositories import DjangoProjectRepository
from studio.models import ProjectModel


class ProjectTypeFilterFixtureMixin:
    def _create_fixtures(self, user):
        ProjectModel.objects.create(name='Pedalada', owner=user, project_type=ProjectModel.ProjectType.GOPRO)
        ProjectModel.objects.create(name='Trilha', owner=user, project_type=ProjectModel.ProjectType.GOPRO)
        ProjectModel.objects.create(name='Final da Copa', owner=user, project_type=ProjectModel.ProjectType.FUTEBOL)


class RepositoryFilterTests(ProjectTypeFilterFixtureMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='coach', password='x')
        self._create_fixtures(self.user)

    def test_no_filter_returns_all(self):
        repo = DjangoProjectRepository(owner=self.user)
        self.assertEqual(len(repo.list()), 3)

    def test_filters_by_gopro(self):
        repo = DjangoProjectRepository(owner=self.user)
        result = repo.list(project_type='gopro')
        self.assertEqual(len(result), 2)
        self.assertTrue(all(p.project_type == 'gopro' for p in result))

    def test_filters_by_futebol(self):
        repo = DjangoProjectRepository(owner=self.user)
        result = repo.list(project_type='futebol')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, 'Final da Copa')


class ListProjectsUseCaseTests(ProjectTypeFilterFixtureMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='coach', password='x')
        self._create_fixtures(self.user)
        self.repo = DjangoProjectRepository(owner=self.user)

    def test_invalid_type_is_ignored(self):
        result = ListProjects(self.repo).execute(project_type='not-a-real-type')
        self.assertEqual(len(result), 3)

    def test_valid_type_filters(self):
        result = ListProjects(self.repo).execute(project_type='futebol')
        self.assertEqual(len(result), 1)


class ProjectListViewFilterTests(ProjectTypeFilterFixtureMixin, TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='coach', password='x')
        self.client.force_login(self.user)
        self._create_fixtures(self.user)

    def test_no_query_param_lists_all(self):
        resp = self.client.get('/projects/')
        self.assertEqual(len(resp.context['projects']), 3)
        self.assertEqual(resp.context['type_filter'], 'all')

    def test_filters_by_type_query_param(self):
        resp = self.client.get('/projects/?type=futebol')
        self.assertEqual(len(resp.context['projects']), 1)
        self.assertEqual(resp.context['type_filter'], 'futebol')

    def test_invalid_type_query_param_falls_back_to_all(self):
        resp = self.client.get('/projects/?type=bogus')
        self.assertEqual(len(resp.context['projects']), 3)
        self.assertEqual(resp.context['type_filter'], 'all')
