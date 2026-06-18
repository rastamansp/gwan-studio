from django.urls import path
from presentation.views import projects

urlpatterns = [
    path('', projects.project_list, name='project-list'),
    path('projects/new/', projects.project_new, name='project-new'),
    path('projects/<str:project_id>/', projects.project_detail, name='project-detail'),
    path('projects/<str:project_id>/sources/', projects.sources_step, name='sources-step'),
    path('projects/<str:project_id>/merge/', projects.merge_step, name='merge-step'),
    path('projects/<str:project_id>/export/', projects.export_step, name='export-step'),
    path('projects/<str:project_id>/thumbnail/', projects.thumbnail_step, name='thumbnail-step'),
    path('projects/<str:project_id>/seo/', projects.seo_step, name='seo-step'),
    path('projects/<str:project_id>/publish/', projects.publish_step, name='publish-step'),
    path('api/health/', projects.health_check, name='health-check'),
]
