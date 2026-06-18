"""
Fase A — F01 + F02: Project CRUD + Source Upload.
"""
import json
import subprocess
import uuid

from django.conf import settings
from django.core.files.storage import default_storage
from django.http import Http404, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

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

# Mock step content substituído progressivamente (F03+)
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
        'Nessa aventura incrível, pedalei 200 km em apenas 3 dias pela belíssima Serra Gaúcha.\n\n'
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

# ── format helpers ─────────────────────────────────────────────

def _fmt_duration(seconds: int) -> str:
    if not seconds:
        return '—'
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def _fmt_size(size_bytes: int) -> str:
    if not size_bytes:
        return '—'
    mb = size_bytes / (1024 * 1024)
    if mb >= 1024:
        return f"{mb / 1024:.1f} GB"
    return f"{mb:.0f} MB"


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


def _probe_duration(file_path: str) -> int:
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', file_path],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        return int(float(data['format']['duration']))
    except Exception:
        return 0

# ── source helpers ─────────────────────────────────────────────

def _list_sources_display(project_id: str) -> list[dict]:
    from studio.models import SourceModel
    return [
        {
            'id':                str(s.id),
            'original_filename': s.original_filename,
            'camera':            s.camera or '—',
            'duration_sec':      s.duration_sec,
            'duration_fmt':      _fmt_duration(s.duration_sec),
            'size_bytes':        s.size_bytes,
            'size_fmt':          _fmt_size(s.size_bytes),
            'status':            s.status,
            'sort_order':        s.sort_order,
        }
        for s in SourceModel.objects.filter(project_id=project_id)
    ]


def _total_duration(sources: list[dict]) -> str:
    total = sum(s['duration_sec'] for s in sources)
    return _fmt_duration(total) if total else '—'

# ── project helpers ────────────────────────────────────────────

def _repo():
    return DjangoProjectRepository()


def _to_display(project, sources: list[dict] | None = None) -> dict:
    if sources is None:
        sources = _list_sources_display(project.id)
    label, color = PHASE_LABELS.get(project.phase, ('—', 'neutral'))
    return {
        'id':            project.id,
        'name':          project.name,
        'channel_name':  project.channel_name or '—',
        'phase':         project.phase,
        'phase_label':   label,
        'phase_color':   color,
        'sources_count': len(sources),
        'total_duration': _total_duration(sources),
        'updated_at':    _fmt_dt(project.updated_at or project.created_at),
    }


def _build_steps(pd: dict, active_key: str) -> list[dict]:
    phase_idx = PHASE_STEP_INDEX.get(pd['phase'], 0)
    return [
        {
            'key':     key,
            'label':   label,
            'url':     f"/projects/{pd['id']}/{key}/",
            'enabled': i <= phase_idx,
            'done':    i < phase_idx,
            'active':  key == active_key,
            'index':   i + 1,
        }
        for i, (key, label) in enumerate(STEPS_META)
    ]


def _step_ctx(pd: dict, active_key: str, extra: dict | None = None) -> dict:
    steps = _build_steps(pd, active_key)
    ctx = {
        'project':     pd,
        'steps':       steps,
        'steps_done':  sum(1 for s in steps if s['done']),
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

# ── Project list / create ──────────────────────────────────────

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
        from application.projects.use_cases import CreateProject
        project = CreateProject(_repo()).execute(name, channel_name)
        return redirect(f'/projects/{project.id}/')
    return redirect('/')

# ── Project detail + step views ────────────────────────────────

def project_detail(request, project_id):
    pd = _get_or_404(project_id)
    sources = _list_sources_display(project_id)
    ctx = _step_ctx(pd, 'sources', {
        'sources': sources,
        'active_template': 'sources/_dropzone.html',
    })
    return render(request, 'projects/detail.html', ctx)


def sources_step(request, project_id):
    pd = _get_or_404(project_id)
    sources = _list_sources_display(project_id)
    extra = {'sources': sources}
    if request.htmx:
        return render(request, 'sources/_dropzone.html', {'project': pd, **extra})
    ctx = _step_ctx(pd, 'sources', {**extra, 'active_template': 'sources/_dropzone.html'})
    return render(request, 'projects/detail.html', ctx)


def merge_step(request, project_id):
    pd = _get_or_404(project_id)
    sources = _list_sources_display(project_id)
    extra = {'sources': sources, 'job_logs': _MOCK_JOB_LOGS}
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

# ── F02: Source upload / delete / list ────────────────────────

def upload_source(request, project_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    # Validar projeto
    from studio.models import ProjectModel
    try:
        project_obj = ProjectModel.objects.get(id=project_id)
    except ProjectModel.DoesNotExist:
        return JsonResponse({'error': 'Projeto não encontrado'}, status=404)

    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'error': 'Arquivo não enviado'}, status=400)

    # Validar extensão
    ext = file.name.rsplit('.', 1)[-1].lower() if '.' in file.name else ''
    allowed = getattr(settings, 'ALLOWED_VIDEO_EXTS', ['mp4', 'mov', 'avi', 'mkv'])
    if ext not in allowed:
        return JsonResponse({'error': f'Formato .{ext} não suportado. Use: {", ".join(allowed)}'}, status=400)

    # Validar tamanho
    max_bytes = getattr(settings, 'MAX_SOURCE_MB', 2048) * 1024 * 1024
    if file.size > max_bytes:
        return JsonResponse({'error': f'Arquivo excede {settings.MAX_SOURCE_MB} MB'}, status=400)

    source_id = str(uuid.uuid4())
    camera = request.POST.get('camera', '').strip()

    # Salvar arquivo em MEDIA_ROOT
    storage_key = f"studio/{project_id}/sources/{source_id}-{file.name}"
    default_storage.save(storage_key, file)

    # Tentar extrair duração via ffprobe
    try:
        full_path = default_storage.path(storage_key)
        duration_sec = _probe_duration(full_path)
    except NotImplementedError:
        duration_sec = 0

    # Criar registro no banco
    from studio.models import SourceModel
    count = SourceModel.objects.filter(project=project_obj).count()
    source = SourceModel.objects.create(
        id=source_id,
        project=project_obj,
        original_filename=file.name,
        camera=camera,
        duration_sec=duration_sec,
        size_bytes=file.size,
        status='ready',
        storage_key=storage_key,
        sort_order=count,
    )

    # Avançar fase do projeto se ainda em 'new'
    if project_obj.phase == 'new':
        project_obj.phase = 'sources_uploaded'
        project_obj.save(update_fields=['phase', 'updated_at'])

    return JsonResponse({
        'id':                str(source.id),
        'original_filename': source.original_filename,
        'camera':            source.camera or '—',
        'duration_sec':      source.duration_sec,
        'duration_fmt':      _fmt_duration(source.duration_sec),
        'size_bytes':        source.size_bytes,
        'size_fmt':          _fmt_size(source.size_bytes),
        'status':            source.status,
        'sort_order':        source.sort_order,
    })


def delete_source(request, project_id, source_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    from studio.models import SourceModel
    try:
        source = SourceModel.objects.get(id=source_id, project_id=project_id)
    except SourceModel.DoesNotExist:
        return JsonResponse({'error': 'Source não encontrado'}, status=404)

    # Deletar arquivo do storage
    if source.storage_key:
        try:
            default_storage.delete(source.storage_key)
        except Exception:
            pass

    source.delete()

    # Retornar lista atualizada (HTMX swap)
    pd = _get_or_404(project_id)
    sources = _list_sources_display(project_id)
    return render(request, 'sources/_source_list.html', {'project': pd, 'sources': sources})


def source_list_partial(request, project_id):
    pd = _get_or_404(project_id)
    sources = _list_sources_display(project_id)
    return render(request, 'sources/_source_list.html', {'project': pd, 'sources': sources})


def health_check(request):
    return JsonResponse({'status': 'ok'})
