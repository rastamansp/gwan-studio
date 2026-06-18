from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from presentation.views import projects

urlpatterns = [
    path('', projects.project_list, name='project-list'),
    path('projects/new/', projects.project_new, name='project-new'),
    path('projects/<str:project_id>/', projects.project_detail, name='project-detail'),
    # Sources step + F02 endpoints
    path('projects/<str:project_id>/sources/', projects.sources_step, name='sources-step'),
    path('projects/<str:project_id>/sources/upload/', projects.upload_source, name='source-upload'),
    path('projects/<str:project_id>/sources/list/', projects.source_list_partial, name='source-list'),
    path('projects/<str:project_id>/sources/<str:source_id>/delete/', projects.delete_source, name='source-delete'),
    # Pipeline steps — Merge (F03)
    path('projects/<str:project_id>/merge/', projects.merge_step, name='merge-step'),
    path('projects/<str:project_id>/merge/start/', projects.merge_start, name='merge-start'),
    path('projects/<str:project_id>/merge/status/', projects.merge_status, name='merge-status'),
    path('projects/<str:project_id>/export/', projects.export_step, name='export-step'),
    path('projects/<str:project_id>/export/start/', projects.export_start, name='export-start'),
    path('projects/<str:project_id>/export/status/', projects.export_status, name='export-status'),
    path('projects/<str:project_id>/export/download/', projects.export_download, name='export-download'),
    path('projects/<str:project_id>/thumbnail/', projects.thumbnail_step, name='thumbnail-step'),
    path('projects/<str:project_id>/thumbnail/generate/', projects.thumbnail_generate, name='thumbnail-generate'),
    path('projects/<str:project_id>/thumbnail/status/', projects.thumbnail_status, name='thumbnail-status'),
    path('projects/<str:project_id>/thumbnail/select/', projects.thumbnail_select, name='thumbnail-select'),
    path('projects/<str:project_id>/thumbnail/image/<str:variant>/', projects.thumbnail_image, name='thumbnail-image'),
    path('projects/<str:project_id>/seo/', projects.seo_step, name='seo-step'),
    path('projects/<str:project_id>/publish/', projects.publish_step, name='publish-step'),
    path('api/health/', projects.health_check, name='health-check'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
