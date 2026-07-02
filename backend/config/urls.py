from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.urls import path

from presentation.views import projects


urlpatterns = [
    path('', projects.home, name='home'),
    path('admin/', admin.site.urls),
    path('register/', projects.register, name='register'),
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='auth/login.html',
            redirect_authenticated_user=True,
        ),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('dashboard/', login_required(projects.dashboard), name='dashboard'),
    path('projects/', login_required(projects.project_list), name='project-list'),
    path('projects/new/', login_required(projects.project_new), name='project-new'),
    path('projects/<str:project_id>/', login_required(projects.project_detail), name='project-detail'),
    path('projects/<str:project_id>/sources/', login_required(projects.sources_step), name='sources-step'),
    path('projects/<str:project_id>/sources/upload/', login_required(projects.upload_source), name='source-upload'),
    path('projects/<str:project_id>/sources/list/', login_required(projects.source_list_partial), name='source-list'),
    path(
        'projects/<str:project_id>/sources/<str:source_id>/delete/',
        login_required(projects.delete_source),
        name='source-delete',
    ),
    path(
        'projects/<str:project_id>/sources/<str:source_id>/preview/',
        login_required(projects.source_preview),
        name='source-preview',
    ),
    path('projects/<str:project_id>/merge/', login_required(projects.merge_step), name='merge-step'),
    path('projects/<str:project_id>/merge/start/', login_required(projects.merge_start), name='merge-start'),
    path('projects/<str:project_id>/merge/status/', login_required(projects.merge_status), name='merge-status'),
    path(
        'projects/<str:project_id>/highlights/',
        login_required(projects.highlights_step),
        name='highlights-step',
    ),
    path(
        'projects/<str:project_id>/highlights/start/',
        login_required(projects.highlights_start),
        name='highlights-start',
    ),
    path(
        'projects/<str:project_id>/highlights/status/',
        login_required(projects.highlights_status),
        name='highlights-status',
    ),
    path(
        'projects/<str:project_id>/highlights/editor/',
        login_required(projects.highlights_editor),
        name='highlights-editor',
    ),
    path(
        'projects/<str:project_id>/highlights/editor/save/',
        login_required(projects.highlights_editor_save),
        name='highlights-editor-save',
    ),
    path(
        'projects/<str:project_id>/highlights/<str:moment_id>/toggle/',
        login_required(projects.highlight_toggle),
        name='highlight-toggle',
    ),
    path('projects/<str:project_id>/export/', login_required(projects.export_step), name='export-step'),
    path('projects/<str:project_id>/export/start/', login_required(projects.export_start), name='export-start'),
    path('projects/<str:project_id>/export/status/', login_required(projects.export_status), name='export-status'),
    path(
        'projects/<str:project_id>/export/download/',
        login_required(projects.export_download),
        name='export-download',
    ),
    path(
        'projects/<str:project_id>/export/preview/',
        login_required(projects.export_preview),
        name='export-preview',
    ),
    path('projects/<str:project_id>/thumbnail/', login_required(projects.thumbnail_step), name='thumbnail-step'),
    path(
        'projects/<str:project_id>/thumbnail/generate/',
        login_required(projects.thumbnail_generate),
        name='thumbnail-generate',
    ),
    path(
        'projects/<str:project_id>/thumbnail/status/',
        login_required(projects.thumbnail_status),
        name='thumbnail-status',
    ),
    path(
        'projects/<str:project_id>/thumbnail/select/',
        login_required(projects.thumbnail_select),
        name='thumbnail-select',
    ),
    path(
        'projects/<str:project_id>/thumbnail/image/<str:variant>/',
        login_required(projects.thumbnail_image),
        name='thumbnail-image',
    ),
    path('projects/<str:project_id>/seo/', login_required(projects.seo_step), name='seo-step'),
    path('projects/<str:project_id>/seo/generate/', login_required(projects.seo_generate), name='seo-generate'),
    path('projects/<str:project_id>/seo/status/', login_required(projects.seo_status), name='seo-status'),
    path('projects/<str:project_id>/seo/save/', login_required(projects.seo_save), name='seo-save'),
    path('projects/<str:project_id>/seo/approve/', login_required(projects.seo_approve), name='seo-approve'),
    path('projects/<str:project_id>/publish/', login_required(projects.publish_step), name='publish-step'),
    path(
        'projects/<str:project_id>/publish/oauth/connect/',
        login_required(projects.publish_oauth_connect),
        name='publish-oauth-connect',
    ),
    path(
        'projects/<str:project_id>/publish/oauth/disconnect/',
        login_required(projects.publish_oauth_disconnect),
        name='publish-oauth-disconnect',
    ),
    path(
        'projects/<str:project_id>/publish/oauth/callback/',
        login_required(projects.publish_oauth_callback),
        name='publish-oauth-callback',
    ),
    path('projects/<str:project_id>/publish/start/', login_required(projects.publish_start), name='publish-start'),
    path(
        'projects/<str:project_id>/publish/status/',
        login_required(projects.publish_status),
        name='publish-status',
    ),
    path('api/health/', projects.health_check, name='health-check'),
    path('api/projects/<str:project_id>/jobs/', login_required(projects.api_job_list), name='api-job-list'),
    path(
        'api/projects/<str:project_id>/jobs/highlight-detect/',
        login_required(projects.api_highlight_detect),
        name='api-highlight-detect',
    ),
    path(
        'api/projects/<str:project_id>/jobs/<str:job_id>/',
        login_required(projects.api_job_detail),
        name='api-job-detail',
    ),
    path(
        'api/projects/<str:project_id>/highlights/',
        login_required(projects.api_highlight_list),
        name='api-highlight-list',
    ),
    path(
        'api/projects/<str:project_id>/highlights/<str:highlight_id>/',
        login_required(projects.api_highlight_update),
        name='api-highlight-update',
    ),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
