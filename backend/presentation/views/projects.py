"""
Fase A — F01: Project CRUD real com ORM Django.
Step content permanece mock até F02 (sources) e F03+ (merge/export/etc.).
"""
from django.shortcuts import render, redirect
from django.http import Http404, JsonResponse
from django.utils import timezone

from application.projects.use_cases import ListProjects, CreateProject, GetProject
from infrastructure.orm.repositories import DjangoProjectRepository

# ── display constants ──────────────────────────────────────────

PHASE_LABELS = {
    'new':              ('Novo',             'neutral'),
    'sources_uploaded': ('Fontes Enviadas',  'info'),
    'merge_done':       ('Merge Concluído',  'warning'),
    'export_done':      ('Export Pronto',    'warning'),
    'thumbnails_done':  ('Thumbnails OK',    'warning'),
    'seo_approved':     ('SEO Aprovado',     'success'),
}

PHASE_STEP_INDEX = {
    'new':              0,
    'sources_uploaded': 1,
    'merge_done':       2,
    'export_done':      3,
    'thumbnails_done':  4,
    'seo_approved':     5,
}

STEPS_META = [
    ('sources',   'Fontes'),
    ('merge',     'Merge'),
    ('export',    'Export'),
    ('thumbnail', 'Thumbnails'),
    ('seo',       'SEO'),
    ('publish',   'Publicar'),
]

# Mock step content (substituído fase a fase em F02+)
_MOCK_SOURCES = [
    {'id': 's1', 'original_filename': 'GoPro_001.mp4', 'camera': 'GoPro Hero 12',
     'duration_sec': 1234, 'duration_fmt': '20m 34s', 'file_size_mb': 4.2, 'status': 'ready'},
    {'id': 's2', 'original_filename': 'GoPro_002.mp4', 'camera': 'GoPro Hero 12',
     'duration_sec': 987,  'duration_fmt': '16m 27s', 'file_size_mb': 3.8, 'status': 'ready'},
    {'id': 's3', 'original_filename': 'iPhone_001.mp4', 'camera': 'iPhone 15 Pro',
     'duration_sec': 456,  'duration_fmt': '7m 36s',  'file_size_mb': 2.1, 'status': 'ready'},
]

_MOCK_JOB_LOGS = [
    {'text': '[00:00] Iniciando merge de 3 fontes...', 'type': 'info'},
    {'text': '[00:02] ffmpeg: concat filter aplicado',  'type': 'info'},
    {'text': '[00:15] ffmpeg: processando 00:01:00 / 00:02:34', 'type': 'progress'},
    {'text': '[00:28] ffmpeg: processando 00:02:00 / 00:02:34', 'type': 'progress'},
    {'text': '[00:31] ffmpeg: concluído — merged.mp4 (287 MB)', 'type': 'success'},
    {'text': '[00:32] Upload para MinIO: studio/…/merged.mp4 ✓', 'type': 'upload'},
]

_MOCK_SEO = {
    'title': 'Como eu pedalei 200 km em 3 dias pela Serra Gaúcha 🚴',
    'description': (
        'Nessa aventura incrível, pedalei 200 km em apenas 3 dias pela belíssima Serra Gaúcha, '
        'passando por vinícolas, paisagens de tirar o fôlego e subidas que testaram os meus limites.\n\n'
        '⏱ Capítulos:\n00:00 - Introdução\n01:20 - Dia 1\n15:40 - Dia 2\n38:00 - Dia 3'
    ),
    'tags': ['ciclismo', 'serra gaúcha', 'cycling', 'bike touring', 'GoPro', 'viagem de bike', 'RS'],
}

_MOCK_THUMBNAILS = [
    {'id': 'A', 'description': 'Frame de subida dramática',
     'gradient': 'from-orange-950 via-red-900 to-amber-800',
     'overlay_top': '🏔️ 200 KM', 'overlay_sub': 'Serra Gaúcha', 'tag': 'Alta intensidade'},
    {'id': 'B', 'description': 'Vista panorâmica das vinícolas',
     'gradient': 'from-emerald-950 via-green-900 to-teal-800',
     'overlay_top': '🍇 ROTA COMPLETA', 'overlay_sub': '3 Dias de Pedal', 'tag': 'Paisagem'},
    {'id': 'C', 'description': 'Selfie no topo, badge 200 km',
     'gradient': 'from-blue-950 via-indigo-900 to-violet-800',
     'overlay_top': '🏆 COMPLETEI', 'overlay_sub': '200 km em 3 dias', 'tag': 'Conquista'},
]

# ── helpers ────────────────────────────────────────────────────

def _repo():
    return DjangoProjectRepository()


def _fmt_dt(dt) -> str:
    if dt is None:
        return '—'
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    now = timezone.now()
    delta = now - dt
    if delta.days == 0:
        return f"Hoje, {dt.astimezone().strftime('%H:%M')}"
    if delta.days == 1:
        return f"Ontem, {dt.astimezone().strftime('%H:%M')}"
    return f"{delta.days} dias atrás"


def _to_display(project) -> dict:
    label, color = PHASE_LABELS.get(project.phase, ('—', 'neutral'))
    return {
        'id': project.id,
        'name': project.name,
        'channel_name': project.channel_name or '—',
        'phase': project.phase,
        'phase_label': label,
        'phase_color': color,
        'sources_count': 0,       # populado em F02
        'total_duration': '—',    # populado em F02
        'updated_at': _fmt_dt(project.updated_at or project.created_at),
    }


def _build_steps(pd: dict, active_key: str) -> list[dict]:
    phase_idx = PHASE_STEP_INDEX.get(pd['phase'], 0)
    return [
        {
            'key': key,
            'label': label,
            'url': f"/projects/{pd['id']}/{key}/",
            'enabled': i <= phase_idx,
            'done': i < phase_idx,
            'active': key == active_key,
            'index': i + 1,
        }
        for i, (key, label) in enumerate(STEPS_META)
    ]


def _step_ctx(pd: dict, active_key: str, extra: dict | None = None) -> dict:
    steps = _build_steps(pd, active_key)
    ctx = {
        'project': pd,
        'steps': steps,
        'steps_done': sum(1 for s in steps if s['done']),
        'steps_total': len(steps),
        'active_step': active_key,
    }
    if extra:
        ctx.update(extra)
    return ctx


def _get_or_404(project_id: str) -> dict:
    try:
        return _to_display(_repo().get(project_id))
    except Exception:
        raise Http404


# ── views ──────────────────────────────────────────────────────

def project_list(request):
    projects = [_to_display(p) for p in _repo().list()]
    return render(request, 'projects/list.html', {'projects': projects})


def project_new(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        channel_name = request.POST.get('channel_name', '').strip()
        if not name:
            projects = [_to_display(p) for p in _repo().list()]
            return render(request, 'projects/list.html', {
                'projects': projects,
                'form_error': 'O nome do projeto é obrigatório.',
            })
        project = CreateProject(_repo()).execute(name, channel_name)
        return redirect(f'/projects/{project.id}/')
    return redirect('/')


def project_detail(request, project_id):
    pd = _get_or_404(project_id)
    ctx = _step_ctx(pd, 'sources', {
        'sources': _MOCK_SOURCES,
        'active_template': 'sources/_dropzone.html',
    })
    return render(request, 'projects/detail.html', ctx)


def sources_step(request, project_id):
    pd = _get_or_404(project_id)
    extra = {'sources': _MOCK_SOURCES}
    if request.htmx:
        return render(request, 'sources/_dropzone.html', {'project': pd, **extra})
    ctx = _step_ctx(pd, 'sources', {**extra, 'active_template': 'sources/_dropzone.html'})
    return render(request, 'projects/detail.html', ctx)


def merge_step(request, project_id):
    pd = _get_or_404(project_id)
    extra = {'sources': _MOCK_SOURCES, 'job_logs': _MOCK_JOB_LOGS}
    if request.htmx:
        return render(request, 'merge/_editor.html', {'project': pd, **extra})
    ctx = _step_ctx(pd, 'merge', {**extra, 'active_template': 'merge/_editor.html'})
    return render(request, 'projects/detail.html', ctx)


def export_step(request, project_id):
    pd = _get_or_404(project_id)
    extra = {'job_logs': _MOCK_JOB_LOGS}
    if request.htmx:
        return render(request, 'export/_settings.html', {'project': pd, **extra})
    ctx = _step_ctx(pd, 'export', {**extra, 'active_template': 'export/_settings.html'})
    return render(request, 'projects/detail.html', ctx)


def thumbnail_step(request, project_id):
    pd = _get_or_404(project_id)
    extra = {'thumbnail_variants': _MOCK_THUMBNAILS}
    if request.htmx:
        return render(request, 'thumbnail/_generator.html', {'project': pd, **extra})
    ctx = _step_ctx(pd, 'thumbnail', {**extra, 'active_template': 'thumbnail/_generator.html'})
    return render(request, 'projects/detail.html', ctx)


def seo_step(request, project_id):
    pd = _get_or_404(project_id)
    extra = {'seo': _MOCK_SEO}
    if request.htmx:
        return render(request, 'seo/_generator.html', {'project': pd, **extra})
    ctx = _step_ctx(pd, 'seo', {**extra, 'active_template': 'seo/_generator.html'})
    return render(request, 'projects/detail.html', ctx)


def publish_step(request, project_id):
    pd = _get_or_404(project_id)
    if request.htmx:
        return render(request, 'publish/_oauth.html', {'project': pd})
    ctx = _step_ctx(pd, 'publish', {'active_template': 'publish/_oauth.html'})
    return render(request, 'projects/detail.html', ctx)


def health_check(request):
    return JsonResponse({'status': 'ok'})
