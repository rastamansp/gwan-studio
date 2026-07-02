"""
Fase A — F01 + F02 + F03: Project CRUD + Source Upload + Merge FFmpeg.
"""
import json
import os
import subprocess
import threading
import time
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.http import Http404, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone

from infrastructure.orm.repositories import DjangoProjectRepository
from infrastructure.storage import get_storage
from presentation.forms import StudioUserCreationForm

# ── display constants ──────────────────────────────────────────

PHASE_LABELS = {
    'new':              ('Novo',                   'neutral'),
    'sources_uploaded': ('Fontes Enviadas',        'info'),
    'merge_done':       ('Merge Concluído',        'warning'),
    'highlights_done':  ('Highlights Detectados',  'warning'),
    'export_done':      ('Export Pronto',          'warning'),
    'thumbnails_done':  ('Thumbnails OK',          'warning'),
    'seo_approved':     ('SEO Aprovado',           'success'),
    'published':        ('Publicado',              'success'),
}

PHASE_STEP_INDEX = {
    'new':              0,
    'sources_uploaded': 1,
    'merge_done':       2,
    'highlights_done':  2,
    'export_done':      3,
    'thumbnails_done':  4,
    'seo_approved':     5,
    'published':        5,
}

# Pipeline "Go Pro" (F03): merge manual de clipes.
STEPS_META = [
    ('sources',   'Fontes'),
    ('merge',     'Merge'),
    ('export',    'Export'),
    ('thumbnail', 'Thumbnails'),
    ('seo',       'SEO'),
    ('publish',   'Publicar'),
]

# Pipeline "Futebol" (F17): detecção automática de highlights substitui o merge manual.
STEPS_META_FUTEBOL = [
    ('sources',    'Fontes'),
    ('highlights', 'Highlights'),
    ('export',     'Export'),
    ('thumbnail',  'Thumbnails'),
    ('seo',        'SEO'),
    ('publish',    'Publicar'),
]


def _steps_meta_for(project_type: str) -> list[tuple[str, str]]:
    return STEPS_META_FUTEBOL if project_type == 'futebol' else STEPS_META


# RN-F17-04 — fases em que o projeto já passou pelo Export; a partir daqui o
# highlight-detect não pode mais reprocessar/substituir os HighlightMoment.
EXPORTED_PHASES = {'export_done', 'thumbnails_done', 'seo_approved', 'published'}


def _project_is_exported(project_obj) -> bool:
    return project_obj.phase in EXPORTED_PHASES

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

# ── F09: WS event emission ─────────────────────────────────────

def _emit_job_event(project_id: str, event: dict) -> None:
    """Append a job event to the in-process WS store; never crashes callers."""
    try:
        from infrastructure.ws.event_store import append_event
        append_event(project_id, event)
    except Exception:
        pass

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


def _log_type(line: str) -> str:
    l = line.lower()
    if l.startswith('[ok]') or 'concluído' in l or 'concluido' in l:
        return 'success'
    if 'non-monotonic dts' in l or 'incorrect timestamps' in l:
        return 'warning'
    if any(k in l for k in ('error', 'invalid', 'failed', 'no such')):
        return 'error'
    if any(k in l for k in ('frame=', 'time=', 'speed=', 'bitrate=')):
        return 'progress'
    if any(k in l for k in ('muxing overhead', 'encoded', 'simulado', 'concluído')):
        return 'success'
    if 'upload' in l or 'minio' in l:
        return 'upload'
    return 'info'


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


def _user_repo(user):
    return DjangoProjectRepository(owner=user)


def _project_obj_or_404(request, project_id: str):
    from studio.models import ProjectModel
    try:
        return ProjectModel.objects.get(id=project_id, owner=request.user)
    except ProjectModel.DoesNotExist:
        raise Http404


def _to_display(project, sources: list[dict] | None = None) -> dict:
    if sources is None:
        sources = _list_sources_display(project.id)
    label, color = PHASE_LABELS.get(project.phase, ('—', 'neutral'))
    return {
        'id':            project.id,
        'name':          project.name,
        'channel_name':  project.channel_name or '—',
        'project_type':  project.project_type,
        'is_futebol':    project.project_type == 'futebol',
        'highlight_settings': project.highlight_settings or {},
        'phase':         project.phase,
        'phase_label':   label,
        'phase_color':   color,
        'sources_count': len(sources),
        'total_duration': _total_duration(sources),
        'updated_at':    _fmt_dt(project.updated_at or project.created_at),
    }


def _build_steps(pd: dict, active_key: str) -> list[dict]:
    phase_idx = PHASE_STEP_INDEX.get(pd['phase'], 0)
    steps_meta = _steps_meta_for(pd.get('project_type', 'gopro'))
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
        for i, (key, label) in enumerate(steps_meta)
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


def _get_or_404(project_id: str, user=None) -> dict:
    try:
        repo = _user_repo(user) if user is not None else _repo()
        return _to_display(repo.get(project_id))
    except Exception:
        raise Http404

# ── Project list / create ──────────────────────────────────────

def home(request):
    return render(request, 'home.html')


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = StudioUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Conta criada com sucesso. Bem-vindo ao Studio.')
            return redirect('dashboard')
    else:
        form = StudioUserCreationForm()

    return render(request, 'auth/register.html', {'form': form})


def dashboard(request):
    projects = [_to_display(p) for p in _user_repo(request.user).list()]
    return render(request, 'dashboard.html', {'projects': projects})


VALID_PROJECT_TYPE_FILTERS = ('gopro', 'futebol')


def project_list(request):
    type_filter = request.GET.get('type')
    type_filter = type_filter if type_filter in VALID_PROJECT_TYPE_FILTERS else None
    projects = [_to_display(p) for p in _user_repo(request.user).list(project_type=type_filter)]
    return render(request, 'projects/list.html', {
        'projects': projects,
        'type_filter': type_filter or 'all',
    })


def project_new(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        channel_name = request.POST.get('channel_name', '').strip()
        project_type = request.POST.get('project_type', 'gopro').strip()
        if not name:
            projects = [_to_display(p) for p in _user_repo(request.user).list()]
            return render(request, 'projects/list.html', {
                'projects': projects,
                'form_error': 'O nome do projeto é obrigatório.',
            })

        highlight_settings = None
        if project_type == 'futebol':
            def _float_field(field, default):
                try:
                    return float(request.POST.get(field, default))
                except (TypeError, ValueError):
                    return default

            def _int_field(field, default):
                try:
                    return int(request.POST.get(field, default))
                except (TypeError, ValueError):
                    return default

            highlight_settings = {
                'pre_roll':         _float_field('pre_roll', 6.0),
                'post_roll':        _float_field('post_roll', 8.0),
                'merge_gap':        _float_field('merge_gap', 4.0),
                'top_n_peaks':      _int_field('top_n_peaks', 40),
                'importancia_min':  _int_field('importancia_min', 5),
            }

        from application.projects.use_cases import CreateProject
        project = CreateProject(_user_repo(request.user)).execute(
            name,
            channel_name,
            owner_id=request.user.id,
            project_type=project_type,
            highlight_settings=highlight_settings,
        )
        return redirect(f'/projects/{project.id}/')
    return redirect('/projects/')

# ── Project detail + step views ────────────────────────────────

def project_detail(request, project_id):
    _project_obj_or_404(request, project_id)
    pd = _get_or_404(project_id, request.user)
    sources = _list_sources_display(project_id)
    ctx = _step_ctx(pd, 'sources', {
        'sources': sources,
        'active_template': 'sources/_dropzone.html',
    })
    return render(request, 'projects/detail.html', ctx)


def sources_step(request, project_id):
    _project_obj_or_404(request, project_id)
    pd = _get_or_404(project_id, request.user)
    sources = _list_sources_display(project_id)
    extra = {'sources': sources}
    if request.htmx:
        return render(request, 'sources/_dropzone.html', {'project': pd, **extra})
    ctx = _step_ctx(pd, 'sources', {**extra, 'active_template': 'sources/_dropzone.html'})
    return render(request, 'projects/detail.html', ctx)


def _latest_merge_job(project_id):
    from studio.models import JobModel
    return (
        JobModel.objects
        .filter(project_id=project_id, job_type='merge')
        .order_by('-created_at')
        .first()
    )


def _job_display(job) -> dict:
    return {
        'id':     str(job.id),
        'status': job.status,
        'error':  job.error,
        'logs':   job.logs or [],
        'result': job.result or {},
    }


def _merge_template_and_ctx(project_id: str) -> tuple[str, dict]:
    """Escolhe template + ctx extra com base no estado do último job de merge."""
    pd = _get_or_404(project_id)
    sources = _list_sources_display(project_id)
    job = _latest_merge_job(project_id)

    if job and job.status == 'running':
        return 'merge/_running.html', {'project': pd, 'sources': sources, 'job': _job_display(job)}

    if job and job.status == 'done':
        result = job.result or {}
        size_fmt = _fmt_size(result.get('size_bytes', 0))
        total_dur = _total_duration(sources)
        return 'merge/_result.html', {
            'project': pd, 'sources': sources,
            'job': _job_display(job),
            'merged_size': size_fmt,
            'merged_duration': total_dur,
            'job_logs': job.logs or [],
        }

    # Nenhum job ou job failed → editor
    return 'merge/_editor.html', {
        'project': pd,
        'sources': sources,
        'sources_json': json.dumps([
            {'id': s['id'], 'original_filename': s['original_filename'],
             'camera': s['camera'], 'duration_fmt': s['duration_fmt'],
             'size_fmt': s['size_fmt']}
            for s in sources
        ]),
        'job_error': job.error if job and job.status == 'failed' else None,
    }


def merge_step(request, project_id):
    _project_obj_or_404(request, project_id)
    template, extra = _merge_template_and_ctx(project_id)
    pd = extra['project']
    if request.htmx:
        return render(request, template, extra)
    ctx = _step_ctx(pd, 'merge', {**extra, 'active_template': template})
    return render(request, 'projects/detail.html', ctx)


def _run_merge_job(job_id: str, source_keys: list[str], output_key: str) -> None:
    """Executa no background thread — chama FFmpeg ou simula; atualiza JobModel."""
    from studio.models import JobModel, ProjectModel
    storage = get_storage()
    try:
        job = JobModel.objects.get(id=job_id)
        project_id = str(job.project_id)
        job.status = 'running'
        job.save(update_fields=['status', 'updated_at'])
        _emit_job_event(project_id, {'event': 'job.update', 'data': {
            'jobId': job_id, 'type': 'merge', 'status': 'running',
        }})

        source_paths = [storage.resolve_read_path(k) for k in source_keys]
        output_path  = storage.resolve_write_path(output_key)

        simulate = getattr(settings, 'MERGE_SIMULATE', False)
        if simulate:
            from infrastructure.ffmpeg.merge import simulate_merge
            log_lines = simulate_merge(source_paths, output_path)
        else:
            from infrastructure.ffmpeg.merge import run_ffmpeg_merge
            log_lines = run_ffmpeg_merge(source_paths, output_path)

        storage.finalize_write(output_key, output_path, 'video/mp4')

        log_dicts = []
        for line in log_lines:
            time.sleep(0.1)
            log_dicts.append({'text': line, 'type': _log_type(line)})
            _emit_job_event(project_id, {'event': 'job.update', 'data': {
                'jobId': job_id, 'type': 'merge', 'status': 'running', 'log_line': line,
            }})

        size_bytes = os.path.getsize(output_path) if os.path.exists(output_path) else 0

        job.status = 'done'
        job.logs = log_dicts
        job.result = {'output_key': output_key, 'size_bytes': size_bytes}
        job.save(update_fields=['status', 'logs', 'result', 'updated_at'])
        ProjectModel.objects.filter(id=project_id).update(phase='merge_done')
        _emit_job_event(project_id, {'event': 'job.update', 'data': {
            'jobId': job_id, 'type': 'merge', 'status': 'done',
            'output_params': {'size_bytes': size_bytes},
        }})

    except Exception as exc:
        try:
            job = JobModel.objects.get(id=job_id)
            project_id = str(job.project_id)
            job.status = 'failed'
            job.error = str(exc)
            job.save(update_fields=['status', 'error', 'updated_at'])
            _emit_job_event(project_id, {'event': 'job.update', 'data': {
                'jobId': job_id, 'type': 'merge', 'status': 'failed', 'error': str(exc),
            }})
        except Exception:
            pass


def merge_start(request, project_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    from studio.models import SourceModel, JobModel
    project_obj = _project_obj_or_404(request, project_id)

    # source_order: lista de IDs enviada pelo frontend (drag-drop)
    raw_order = request.POST.get('source_order', '[]')
    try:
        source_order = json.loads(raw_order)
    except (json.JSONDecodeError, ValueError):
        source_order = []

    # Buscar sources pelo projeto; respeitar ordem do frontend se fornecida
    sources_qs = SourceModel.objects.filter(project=project_obj, status='ready')
    if source_order:
        id_index = {sid: i for i, sid in enumerate(source_order)}
        sources = sorted(sources_qs, key=lambda s: id_index.get(str(s.id), 9999))
    else:
        sources = list(sources_qs.order_by('sort_order', 'created_at'))

    if not sources:
        # Sem sources — retorna editor com erro
        template, ctx = 'merge/_editor.html', {
            'project': _get_or_404(project_id, request.user),
            'sources': [],
            'sources_json': '[]',
            'job_error': 'Adicione pelo menos uma fonte antes de fazer o merge.',
        }
        return render(request, template, ctx)

    # Chaves de storage (sem resolver paths — o job faz isso via porta)
    source_keys = [s.storage_key for s in sources]
    output_key  = f'studio/{project_id}/merged/merged.mp4'

    # Criar job
    job = JobModel.objects.create(
        project=project_obj,
        job_type='merge',
        status='pending',
        source_order=[str(s.id) for s in sources],
    )

    # Disparar thread e retornar imediatamente com o template _running
    t = threading.Thread(
        target=_run_merge_job,
        args=(str(job.id), source_keys, output_key),
        daemon=True,
    )
    t.start()

    pd = _get_or_404(project_id, request.user)
    return render(request, 'merge/_running.html', {
        'project': pd,
        'sources': _list_sources_display(project_id),
        'job': _job_display(job),
    })


def merge_status(request, project_id):
    """Polling HTMX — retorna o template adequado ao estado atual do job."""
    _project_obj_or_404(request, project_id)
    template, ctx = _merge_template_and_ctx(project_id)
    return render(request, template, ctx)


# ── F17: pipeline "Futebol" — detecção automática de highlights ────────

def _latest_highlight_job(project_id):
    from studio.models import JobModel
    return (
        JobModel.objects
        .filter(project_id=project_id, job_type='highlight_detect')
        .order_by('-created_at')
        .first()
    )


def _list_highlight_moments(project_id: str) -> list[dict]:
    """Inclui `source_label` (nome do vídeo de origem) quando o projeto tem
    mais de um source — útil para distinguir 1º/2º tempo, múltiplas câmeras etc."""
    from studio.models import HighlightMomentModel, SourceModel

    sources = list(SourceModel.objects.filter(project_id=project_id).order_by('sort_order', 'created_at'))
    show_source_label = len(sources) > 1
    filenames_by_id = {str(s.id): s.original_filename for s in sources}
    order_by_id = {str(s.id): i + 1 for i, s in enumerate(sources)}

    def _label(source_id: str | None) -> str | None:
        if not show_source_label or not source_id or source_id not in filenames_by_id:
            return None
        return f"{order_by_id[source_id]}º tempo — {filenames_by_id[source_id]}"

    return [
        {
            'id':            str(m.id),
            'source_id':     str(m.source_id) if m.source_id else None,
            'source_label':  _label(str(m.source_id) if m.source_id else None),
            'timestamp_sec': m.timestamp_sec,
            'timestamp_fmt': _fmt_duration(int(m.timestamp_sec)),
            'tipo':          m.tipo,
            'descricao':     m.descricao,
            'importancia':   m.importancia,
            'included':      m.included,
        }
        for m in HighlightMomentModel.objects.filter(project_id=project_id)
    ]


def _highlight_template_and_ctx(project_id: str, force_editor: bool = False) -> tuple[str, dict]:
    pd = _get_or_404(project_id)
    job = _latest_highlight_job(project_id)
    moments = _list_highlight_moments(project_id)

    if job and job.status == 'running':
        return 'highlights/_running.html', {'project': pd, 'job': _job_display(job)}

    is_exported = pd['phase'] in EXPORTED_PHASES

    if not force_editor and job and job.status == 'done' and moments:
        included_count = sum(1 for m in moments if m['included'])
        return 'highlights/_result.html', {
            'project': pd,
            'moments': moments,
            'included_count': included_count,
            'job': _job_display(job),
            'job_logs': job.logs or [],
            'is_exported': is_exported,
        }

    return 'highlights/_editor.html', {
        'project': pd,
        'settings': pd.get('highlight_settings') or {},
        'job_error': job.error if job and job.status == 'failed' else None,
        'is_exported': is_exported,
    }


def highlights_step(request, project_id):
    _project_obj_or_404(request, project_id)
    force_editor = request.GET.get('reprocess') == '1'
    template, extra = _highlight_template_and_ctx(project_id, force_editor=force_editor)
    pd = extra['project']
    if request.htmx:
        return render(request, template, extra)
    ctx = _step_ctx(pd, 'highlights', {**extra, 'active_template': template})
    return render(request, 'projects/detail.html', ctx)


def _persist_highlight_clips(project_id: str, clip_records: list) -> None:
    """F18 — grava o plano de corte (EDL) a partir de `(source, start, end)`.

    Substitui por completo os `HighlightClipModel` anteriores (RN-F18-04):
    reprocessar a detecção sempre reseta ajustes manuais feitos no editor.
    """
    from studio.models import HighlightClipModel
    HighlightClipModel.objects.filter(project_id=project_id).delete()
    HighlightClipModel.objects.bulk_create([
        HighlightClipModel(
            project_id=project_id, source=src, start_sec=start, end_sec=end,
            order=i, included=True,
        )
        for i, (src, start, end) in enumerate(clip_records)
    ])


def _cut_highlight_from_clips(project_id: str, simulate: bool) -> tuple[dict, list[str]]:
    """F18 — (re)gera `merged.mp4` a partir dos `HighlightClipModel.included=True`
    atuais, sem tocar em áudio/Whisper/Claude — só FFmpeg (cut_and_concat)."""
    from studio.models import HighlightClipModel

    storage = get_storage()
    clips = list(
        HighlightClipModel.objects.filter(project_id=project_id, included=True)
        .select_related('source').order_by('order')
    )
    if not clips:
        raise RuntimeError('Nenhum corte incluído — não é possível gerar o highlight.')

    all_clips = [
        (storage.resolve_read_path(clip.source.storage_key), clip.start_sec, clip.end_sec)
        for clip in clips
    ]

    output_key = f'studio/{project_id}/merged/merged.mp4'
    output_path = storage.resolve_write_path(output_key)
    if simulate:
        from infrastructure.ffmpeg.highlights import simulate_cut_and_concat
        cut_logs = simulate_cut_and_concat(all_clips, output_path)
    else:
        from infrastructure.ffmpeg.highlights import cut_and_concat
        cut_logs = cut_and_concat(all_clips, output_path)
    storage.finalize_write(output_key, output_path, 'video/mp4')

    size_bytes = os.path.getsize(output_path) if os.path.exists(output_path) else 0
    result = {'output_key': output_key, 'size_bytes': size_bytes, 'num_clips': len(all_clips)}
    return result, cut_logs


def _run_highlight_job(job_id: str, project_id: str, project_name: str,
                        source_keys: list[str], highlight_settings: dict) -> None:
    """RF03-RF07 — extrai áudio, detecta picos, analisa com Claude e corta o
    highlight final. Isola falhas por source (RN-F17 / REQ-F17-08): um source
    com erro não interrompe o processamento dos demais."""
    from studio.models import JobModel, ProjectModel, SourceModel, HighlightMomentModel
    from domain.highlight_rules import merge_moments

    storage = get_storage()
    logs: list[dict] = []

    def _log(text: str, log_type: str = 'info') -> None:
        logs.append({'text': text, 'type': log_type})
        _emit_job_event(project_id, {'event': 'job.update', 'data': {
            'jobId': job_id, 'type': 'highlight_detect', 'status': 'running', 'log_line': text,
        }})

    try:
        job = JobModel.objects.get(id=job_id)
        job.status = 'running'
        job.save(update_fields=['status', 'updated_at'])
        _emit_job_event(project_id, {'event': 'job.update', 'data': {
            'jobId': job_id, 'type': 'highlight_detect', 'status': 'running',
        }})

        simulate = getattr(settings, 'HIGHLIGHT_SIMULATE', True)
        use_queue = not simulate and getattr(settings, 'HIGHLIGHT_USE_QUEUE', False)
        api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
        pre_roll = highlight_settings.get('pre_roll', 6.0)
        post_roll = highlight_settings.get('post_roll', 8.0)
        merge_gap = highlight_settings.get('merge_gap', 4.0)
        top_n_peaks = highlight_settings.get('top_n_peaks', 40)
        importancia_min = highlight_settings.get('importancia_min', 5)

        HighlightMomentModel.objects.filter(project_id=project_id).delete()

        clip_records: list[tuple] = []  # (source, start, end) — vira HighlightClipModel (F18)
        any_success = False

        for source_key in source_keys:
            source = None
            try:
                source = SourceModel.objects.get(storage_key=source_key, project_id=project_id)
                video_path = storage.resolve_read_path(source_key)
                wav_key = f'studio/{project_id}/tmp/{source.id}.wav'

                if simulate:
                    _log(f'[SIMULADO] Extraindo áudio e detectando picos: {source.original_filename}')
                    from infrastructure.ffmpeg.highlights import simulate_energy_peaks
                    peaks = simulate_energy_peaks(source.duration_sec or 300, top_n_peaks)
                else:
                    _log(f'Extraindo áudio: {source.original_filename}')
                    wav_path = storage.resolve_write_path(wav_key)
                    from infrastructure.ffmpeg.highlights import extract_audio_wav, audio_energy_peaks
                    extract_audio_wav(video_path, wav_path)
                    if use_queue:
                        # Necessário para o highlight-worker (container externo) conseguir
                        # ler o WAV via MinIO — no-op no LocalStorageAdapter.
                        storage.finalize_write(wav_key, wav_path, 'audio/wav')
                    _log(f'Detectando picos de energia: {source.original_filename}')
                    peaks = audio_energy_peaks(wav_path, top_n_peaks)

                _log(f'{len(peaks)} pico(s) candidato(s) — {source.original_filename}', 'success')

                if simulate:
                    from infrastructure.ai.highlight_analyzer import simulate_detect_moments
                    _log(f'[SIMULADO] Analisando picos: {source.original_filename}')
                    raw_moments = simulate_detect_moments(peaks, importancia_min)
                elif use_queue:
                    from infrastructure.messaging.rabbitmq_highlight_client import RabbitMqHighlightWorkerClient
                    _log(f'Aguardando worker (transcrição Whisper + Claude): {source.original_filename}')
                    worker_client = RabbitMqHighlightWorkerClient(
                        url=getattr(settings, 'RABBITMQ_URL', ''),
                        queue=getattr(settings, 'RABBITMQ_HIGHLIGHT_QUEUE', 'highlight.detect'),
                        exchange=getattr(settings, 'RABBITMQ_HIGHLIGHT_EXCHANGE', 'highlight'),
                        routing_key=getattr(settings, 'RABBITMQ_HIGHLIGHT_ROUTING_KEY', 'highlight.results'),
                        timeout_sec=getattr(settings, 'HIGHLIGHT_WORKER_TIMEOUT_SEC', 900),
                    )
                    raw_moments = worker_client.detect_moments(
                        project_id=project_id,
                        source_id=str(source.id),
                        audio_wav_key=wav_key,
                        energy_peaks=peaks,
                        importancia_min=importancia_min,
                    )
                    _log(f'Resposta do worker recebida: {source.original_filename}', 'success')
                else:
                    from infrastructure.ai.highlight_analyzer import ClaudeHighlightAnalyzer
                    _log(f'Analisando com Claude (sem Whisper — adapter provisório): {source.original_filename}')
                    analyzer = ClaudeHighlightAnalyzer(api_key=api_key)
                    raw_moments = analyzer.detect_moments(
                        peaks, source.duration_sec or 0, project_name, importancia_min,
                    )

                for m in raw_moments:
                    HighlightMomentModel.objects.create(
                        project_id=project_id,
                        source=source,
                        timestamp_sec=m['timestamp'],
                        tipo=m.get('tipo', 'outro'),
                        descricao=m.get('descricao', ''),
                        importancia=m.get('importancia', 0),
                        included=True,
                    )

                intervals = merge_moments(
                    raw_moments, source.duration_sec or 0, pre_roll, post_roll, merge_gap,
                )
                clip_records.extend((source, i.start, i.end) for i in intervals)
                _log(f'{len(intervals)} intervalo(s) de corte — {source.original_filename}', 'success')
                any_success = True

            except Exception as source_exc:
                # RN de isolamento (REQ-F17-08): falha em um source não derruba o job inteiro.
                label = source.original_filename if source else source_key
                _log(f'[ERRO] {label}: {source_exc}', 'error')

        if not any_success or not clip_records:
            raise RuntimeError('Nenhum highlight detectado em nenhuma fonte (ajuste importancia_min ou revise o áudio).')

        # F18 — persiste o plano de corte (EDL) editável no editor de timeline.
        _persist_highlight_clips(project_id, clip_records)
        cut_result, cut_logs = _cut_highlight_from_clips(project_id, simulate=simulate)
        for line in cut_logs:
            _log(line, _log_type(line))

        moments_count = HighlightMomentModel.objects.filter(project_id=project_id, included=True).count()

        job.status = 'done'
        job.logs = logs
        job.result = cut_result
        job.save(update_fields=['status', 'logs', 'result', 'updated_at'])
        ProjectModel.objects.filter(id=project_id).update(phase='highlights_done')
        _emit_job_event(project_id, {'event': 'job.update', 'data': {
            'jobId': job_id, 'type': 'highlight_detect', 'status': 'done',
            'output_params': {'size_bytes': cut_result['size_bytes'], 'moments': moments_count},
        }})

    except Exception as exc:
        try:
            job = JobModel.objects.get(id=job_id)
            job.status = 'failed'
            job.error = str(exc)
            job.logs = logs
            job.save(update_fields=['status', 'error', 'logs', 'updated_at'])
            _emit_job_event(project_id, {'event': 'job.update', 'data': {
                'jobId': job_id, 'type': 'highlight_detect', 'status': 'failed', 'error': str(exc),
            }})
        except Exception:
            pass


class HighlightDetectError(Exception):
    """Erro de validação ao iniciar o job de highlight-detect (não é falha do job em si)."""
    def __init__(self, message: str, status: int, code: str = 'invalid'):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code  # 'wrong_type' | 'locked' | 'no_sources'


def _launch_highlight_job(project_obj):
    """REQ-F17-02/RN-F17-04/RN-F17-05 — valida e dispara o job de detecção em background.

    Compartilhado entre a view HTMX (highlights_start) e a API REST
    (api_highlight_detect), para não duplicar a regra de negócio.
    Levanta HighlightDetectError em caso de validação inválida.
    """
    from studio.models import SourceModel, JobModel

    if project_obj.project_type != 'futebol':
        raise HighlightDetectError('job only available for project_type=futebol', 409, code='wrong_type')

    if _project_is_exported(project_obj):
        raise HighlightDetectError(
            'Highlights já foram exportados — reprocessar exigiria refazer o Export. '
            'Volte à etapa Export para gerar o vídeo novamente após revisar os highlights.',
            409, code='locked',
        )

    sources = list(SourceModel.objects.filter(project=project_obj, status='ready'))
    if not sources:
        raise HighlightDetectError(
            'Adicione pelo menos uma fonte antes de detectar highlights.', 400, code='no_sources',
        )

    source_keys = [s.storage_key for s in sources]
    project_id = str(project_obj.id)

    job = JobModel.objects.create(
        project=project_obj,
        job_type='highlight_detect',
        status='pending',
        source_order=[str(s.id) for s in sources],
    )

    t = threading.Thread(
        target=_run_highlight_job,
        args=(
            str(job.id), project_id, project_obj.name,
            source_keys, project_obj.highlight_settings or {},
        ),
        daemon=True,
    )
    t.start()
    return job


def highlights_start(request, project_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    project_obj = _project_obj_or_404(request, project_id)

    try:
        job = _launch_highlight_job(project_obj)
    except HighlightDetectError as exc:
        if exc.code == 'wrong_type':
            # Defensivo — não deveria ser alcançável pela UI (só existe rota p/ futebol).
            return JsonResponse({'error': exc.message}, status=exc.status)
        template, ctx = 'highlights/_editor.html', {
            'project': _get_or_404(project_id, request.user),
            'settings': project_obj.highlight_settings or {},
            'job_error': exc.message,
        }
        return render(request, template, ctx)

    pd = _get_or_404(project_id, request.user)
    return render(request, 'highlights/_running.html', {
        'project': pd,
        'job': _job_display(job),
    })


def highlights_status(request, project_id):
    """Polling HTMX — retorna o template adequado ao estado atual do job."""
    _project_obj_or_404(request, project_id)
    template, ctx = _highlight_template_and_ctx(project_id)
    return render(request, template, ctx)


def highlight_toggle(request, project_id, moment_id):
    """REQ-F17-06 — inclui/exclui manualmente um momento antes do export."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    _project_obj_or_404(request, project_id)

    from studio.models import HighlightMomentModel
    try:
        moment = HighlightMomentModel.objects.get(id=moment_id, project_id=project_id)
    except HighlightMomentModel.DoesNotExist:
        raise Http404

    moment.included = not moment.included
    moment.save(update_fields=['included'])

    template, ctx = _highlight_template_and_ctx(project_id)
    return render(request, template, ctx)


# ── F18: editor de timeline de cortes ───────────────────────────

def highlights_editor(request, project_id):
    """F18 — tela dedicada (fora do wizard de steps) para ajustar manualmente
    os limites de cada corte, arrastando sobre a timeline do vídeo original."""
    project_obj = _project_obj_or_404(request, project_id)
    pd = _get_or_404(project_id, request.user)
    if not pd['is_futebol']:
        raise Http404

    from studio.models import HighlightClipModel, SourceModel

    sources = list(
        SourceModel.objects.filter(project=project_obj, status='ready').order_by('sort_order', 'created_at')
    )
    sources_data = []
    for source in sources:
        clips = HighlightClipModel.objects.filter(project_id=project_id, source=source).order_by('order')
        sources_data.append({
            'source': {
                'id': str(source.id),
                'filename': source.original_filename,
                'duration_sec': source.duration_sec or 0,
            },
            'clips': [
                {
                    'id': str(c.id), 'start_sec': c.start_sec, 'end_sec': c.end_sec,
                    'included': c.included, 'order': c.order,
                }
                for c in clips
            ],
        })

    return render(request, 'highlights/editor.html', {
        'project': pd,
        'sources_data_json': json.dumps(sources_data, ensure_ascii=False),
        'is_exported': pd['phase'] in EXPORTED_PHASES,
    })


def highlights_editor_save(request, project_id):
    """F18 — REQ-F18-06: valida (RN-F18-01/02/03), persiste os cortes editados
    e dispara o recorte (FFmpeg), sem repetir Whisper/Claude."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    _project_obj_or_404(request, project_id)

    from studio.models import HighlightClipModel

    try:
        payload = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'invalid JSON body'}, status=400)

    edits = payload.get('clips', [])
    if not isinstance(edits, list):
        return JsonResponse({'error': 'clips deve ser uma lista'}, status=400)

    clips_by_id = {
        str(c.id): c
        for c in HighlightClipModel.objects.filter(project_id=project_id).select_related('source')
    }

    updates = []
    by_source: dict[str, list] = {}
    for edit in edits:
        clip = clips_by_id.get(str(edit.get('id')))
        if clip is None:
            return JsonResponse({'error': f"clip {edit.get('id')} não encontrado"}, status=404)

        try:
            start = float(edit.get('start_sec', clip.start_sec))
            end = float(edit.get('end_sec', clip.end_sec))
        except (TypeError, ValueError):
            return JsonResponse({'error': 'start_sec/end_sec inválidos'}, status=400)
        included = bool(edit.get('included', clip.included))
        duration = clip.source.duration_sec or 0

        # RN-F18-01/02
        if start < 0 or (duration and end > duration):
            return JsonResponse(
                {'error': f'corte fora dos limites do vídeo ({clip.source.original_filename})'}, status=400,
            )
        if end - start < 0.5:
            return JsonResponse({'error': 'corte precisa ter ao menos 0.5s de duração'}, status=400)

        updates.append((clip, start, end, included))
        by_source.setdefault(str(clip.source_id), []).append((start, end, included))

    # RN-F18-03 — sem sobreposição entre clipes incluídos do mesmo source.
    for items in by_source.values():
        included_items = sorted((i for i in items if i[2]), key=lambda i: i[0])
        for prev, curr in zip(included_items, included_items[1:]):
            if curr[0] < prev[1]:
                return JsonResponse({'error': 'cortes sobrepostos não são permitidos'}, status=400)

    for clip, start, end, included in updates:
        clip.start_sec = start
        clip.end_sec = end
        clip.included = included
        clip.save(update_fields=['start_sec', 'end_sec', 'included'])

    simulate = getattr(settings, 'HIGHLIGHT_SIMULATE', True)
    try:
        result, _logs = _cut_highlight_from_clips(project_id, simulate=simulate)
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    project_obj = _project_obj_or_404(request, project_id)
    return JsonResponse({
        'ok': True,
        'result': result,
        'is_exported': _project_is_exported(project_obj),
    })


def _latest_export_job(project_id):
    from studio.models import JobModel
    return (
        JobModel.objects
        .filter(project_id=project_id, job_type='export')
        .order_by('-created_at')
        .first()
    )


def _export_template_and_ctx(project_id: str) -> tuple[str, dict]:
    pd = _get_or_404(project_id)
    job = _latest_export_job(project_id)

    if job and job.status == 'running':
        return 'export/_running.html', {'project': pd, 'job': _job_display(job)}

    if job and job.status == 'done':
        result = job.result or {}
        return 'export/_result.html', {
            'project': pd,
            'job':            _job_display(job),
            'final_size':     _fmt_size(result.get('size_bytes', 0)),
            'final_codec':    result.get('codec', 'copy'),
            'final_res':      result.get('resolution', 'original'),
            'final_bitrate':  result.get('bitrate', ''),
            'job_logs':       job.logs or [],
        }

    return 'export/_settings.html', {
        'project': pd,
        'job_error': job.error if job and job.status == 'failed' else None,
    }


def export_step(request, project_id):
    _project_obj_or_404(request, project_id)
    template, extra = _export_template_and_ctx(project_id)
    pd = extra['project']
    if request.htmx:
        return render(request, template, extra)
    ctx = _step_ctx(pd, 'export', {**extra, 'active_template': template})
    return render(request, 'projects/detail.html', ctx)


def _run_export_job(
    job_id: str, merged_key: str, final_key: str,
    codec: str, resolution: str, bitrate: str,
) -> None:
    from studio.models import JobModel, ProjectModel
    storage = get_storage()
    try:
        job = JobModel.objects.get(id=job_id)
        project_id = str(job.project_id)
        job.status = 'running'
        job.save(update_fields=['status', 'updated_at'])
        _emit_job_event(project_id, {'event': 'job.update', 'data': {
            'jobId': job_id, 'type': 'export', 'status': 'running',
        }})

        merged_path = storage.resolve_read_path(merged_key)
        output_path = storage.resolve_write_path(final_key)

        simulate = getattr(settings, 'EXPORT_SIMULATE', False)
        if simulate:
            from infrastructure.ffmpeg.export import simulate_export
            log_lines = simulate_export(merged_path, output_path, codec, resolution, bitrate)
        else:
            from infrastructure.ffmpeg.export import run_ffmpeg_export
            log_lines = run_ffmpeg_export(merged_path, output_path, codec, resolution, bitrate)

        storage.finalize_write(final_key, output_path, 'video/mp4')

        log_dicts = []
        for line in log_lines:
            time.sleep(0.1)
            log_dicts.append({'text': line, 'type': _log_type(line)})
            _emit_job_event(project_id, {'event': 'job.update', 'data': {
                'jobId': job_id, 'type': 'export', 'status': 'running', 'log_line': line,
            }})

        size_bytes = os.path.getsize(output_path) if os.path.exists(output_path) else 0

        job.status = 'done'
        job.logs = log_dicts
        job.result = {
            'final_key':  final_key,
            'size_bytes': size_bytes,
            'codec':      codec,
            'resolution': resolution,
            'bitrate':    bitrate,
        }
        job.save(update_fields=['status', 'logs', 'result', 'updated_at'])
        ProjectModel.objects.filter(id=project_id).update(phase='export_done')
        _emit_job_event(project_id, {'event': 'job.update', 'data': {
            'jobId': job_id, 'type': 'export', 'status': 'done',
            'output_params': {'size_bytes': size_bytes, 'codec': codec},
        }})

    except Exception as exc:
        try:
            job = JobModel.objects.get(id=job_id)
            project_id = str(job.project_id)
            job.status = 'failed'
            job.error = str(exc)
            job.save(update_fields=['status', 'error', 'updated_at'])
            _emit_job_event(project_id, {'event': 'job.update', 'data': {
                'jobId': job_id, 'type': 'export', 'status': 'failed', 'error': str(exc),
            }})
        except Exception:
            pass


def export_start(request, project_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    from studio.models import JobModel
    project_obj = _project_obj_or_404(request, project_id)

    codec      = request.POST.get('codec', 'copy').strip()
    resolution = request.POST.get('resolution', 'original').strip()
    bitrate    = request.POST.get('bitrate', '').strip()

    # Validar valores
    if codec not in ('copy', 'h264', 'h265'):
        codec = 'copy'

    merged_key = f'studio/{project_id}/merged/merged.mp4'
    final_key  = f'studio/{project_id}/final/final.mp4'

    job = JobModel.objects.create(
        project=project_obj,
        job_type='export',
        status='pending',
        result={'codec': codec, 'resolution': resolution, 'bitrate': bitrate},
    )

    t = threading.Thread(
        target=_run_export_job,
        args=(str(job.id), merged_key, final_key, codec, resolution, bitrate),
        daemon=True,
    )
    t.start()

    pd = _get_or_404(project_id, request.user)
    return render(request, 'export/_running.html', {
        'project': pd,
        'job': _job_display(job),
    })


def export_status(request, project_id):
    _project_obj_or_404(request, project_id)
    template, ctx = _export_template_and_ctx(project_id)
    return render(request, template, ctx)


def export_download(request, project_id):
    _project_obj_or_404(request, project_id)
    from django.http import FileResponse, Http404, HttpResponseRedirect
    storage = get_storage()
    final_key = f'studio/{project_id}/final/final.mp4'
    if not storage.object_exists(final_key):
        raise Http404
    if storage.is_local:
        return FileResponse(
            open(storage.resolve_read_path(final_key), 'rb'),
            as_attachment=True,
            filename='final.mp4',
            content_type='video/mp4',
        )
    return HttpResponseRedirect(storage.get_presigned_url(final_key, expires=86400))


def export_preview(request, project_id):
    """Stream inline (sem Content-Disposition: attachment) para o `<video>`
    da tela de Export/Publicar — REQ-F07 (pré-visualização antes de publicar)."""
    _project_obj_or_404(request, project_id)
    from django.http import FileResponse, Http404, HttpResponseRedirect
    storage = get_storage()
    final_key = f'studio/{project_id}/final/final.mp4'
    if not storage.object_exists(final_key):
        raise Http404
    if storage.is_local:
        return FileResponse(
            open(storage.resolve_read_path(final_key), 'rb'),
            content_type='video/mp4',
        )
    return HttpResponseRedirect(storage.get_presigned_url(final_key, expires=3600))


def _latest_thumbnail_job(project_id):
    from studio.models import JobModel
    return (
        JobModel.objects
        .filter(project_id=project_id, job_type='thumbnail')
        .order_by('-created_at')
        .first()
    )


def _list_thumbnails(project_id: str) -> list[dict]:
    from studio.models import ThumbnailModel
    storage = get_storage()
    return [
        {
            'id':         str(t.id),
            'variant':    t.variant,
            'plan':       t.plan,
            'output_key': t.output_key,
            'selected':   t.selected,
            'has_image':  bool(t.output_key and storage.object_exists(t.output_key)),
        }
        for t in ThumbnailModel.objects.filter(project_id=project_id)
    ]


def _thumbnail_template_and_ctx(project_id: str) -> tuple[str, dict]:
    pd = _get_or_404(project_id)
    job = _latest_thumbnail_job(project_id)
    thumbnails = _list_thumbnails(project_id)

    if job and job.status == 'running':
        return 'thumbnail/_running.html', {'project': pd, 'job': _job_display(job)}

    if job and job.status == 'done' and thumbnails:
        return 'thumbnail/_result.html', {
            'project': pd,
            'thumbnails': thumbnails,
            'selected': next((t for t in thumbnails if t['selected']), None),
            'job': _job_display(job),
        }

    return 'thumbnail/_generator.html', {
        'project': pd,
        'job_error': job.error if job and job.status == 'failed' else None,
    }


def thumbnail_step(request, project_id):
    _project_obj_or_404(request, project_id)
    template, extra = _thumbnail_template_and_ctx(project_id)
    pd = extra['project']
    if request.htmx:
        return render(request, template, extra)
    ctx = _step_ctx(pd, 'thumbnail', {**extra, 'active_template': template})
    return render(request, 'projects/detail.html', ctx)


def _simulated_plans(project_name: str) -> list[dict]:
    name = project_name[:30]
    return [
        {
            'variant': 'A',
            'description': 'Frame dramático com texto de impacto e fundo vermelho intenso',
            'text_overlay': name.upper(),
            'color_palette': ['#dc2626', '#7f1d1d'],
            'focus_area': 'action',
            'font_style': 'bold',
        },
        {
            'variant': 'B',
            'description': 'Vista panorâmica com legenda limpa sobre fundo azul',
            'text_overlay': name,
            'color_palette': ['#1d4ed8', '#1e3a8a'],
            'focus_area': 'landscape',
            'font_style': 'clean',
        },
        {
            'variant': 'C',
            'description': 'Badge de conquista com destaque verde vibrante',
            'text_overlay': f'✓ {name}',
            'color_palette': ['#16a34a', '#14532d'],
            'focus_area': 'face',
            'font_style': 'dramatic',
        },
    ]


def _run_thumbnail_job(job_id: str, project_id: str, project_name: str) -> None:
    from studio.models import JobModel, ProjectModel, ThumbnailModel
    from infrastructure.image.thumbnail_renderer import render_thumbnail
    logs = []
    try:
        job = JobModel.objects.get(id=job_id)
        job.status = 'running'
        job.save(update_fields=['status', 'updated_at'])
        _emit_job_event(project_id, {'event': 'job.update', 'data': {
            'jobId': job_id, 'type': 'thumbnail', 'status': 'running',
        }})

        simulate = getattr(settings, 'THUMBNAIL_SIMULATE', True)
        storage = get_storage()

        # Escolher vídeo de entrada
        final_key  = f'studio/{project_id}/final/final.mp4'
        merged_key = f'studio/{project_id}/merged/merged.mp4'
        video_key  = final_key if storage.object_exists(final_key) else merged_key
        video_path = storage.resolve_read_path(video_key)

        if simulate:
            plans = _simulated_plans(project_name)
            logs.append({'text': '[SIMULADO] Planos gerados sem Claude Vision', 'type': 'info'})
        else:
            # Extração de frames
            api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
            logs.append({'text': 'Extraindo 6 frames do vídeo…', 'type': 'info'})
            from infrastructure.ffmpeg.frames import extract_frames
            frames_b64 = extract_frames(video_path, n=6)
            logs.append({'text': f'{len(frames_b64)} frames extraídos', 'type': 'success'})

            logs.append({'text': 'Chamando Claude Vision para planejamento…', 'type': 'info'})
            from infrastructure.ai.thumbnail_planner import plan_thumbnails
            plans = plan_thumbnails(frames_b64, project_name, api_key=api_key)
            logs.append({'text': '3 planos recebidos do Claude', 'type': 'success'})

        # Deletar thumbnails anteriores
        ThumbnailModel.objects.filter(project_id=project_id).delete()

        for plan in plans:
            variant = plan.get('variant', 'A')
            thumb_key = f'studio/{project_id}/thumbnails/{variant}.jpg'
            out_path  = storage.resolve_write_path(thumb_key)
            render_thumbnail(plan, variant, out_path)
            storage.finalize_write(thumb_key, out_path, 'image/jpeg')
            ThumbnailModel.objects.create(
                project_id=project_id,
                variant=variant,
                plan=plan,
                output_key=thumb_key,
            )
            log_line = f'Thumbnail {variant} renderizada ({os.path.getsize(out_path)//1024} KB)'
            logs.append({'text': log_line, 'type': 'success'})
            _emit_job_event(project_id, {'event': 'job.update', 'data': {
                'jobId': job_id, 'type': 'thumbnail', 'status': 'running', 'log_line': log_line,
            }})

        job.status = 'done'
        job.logs = logs
        job.result = {'variants': [p.get('variant') for p in plans]}
        job.save(update_fields=['status', 'logs', 'result', 'updated_at'])
        ProjectModel.objects.filter(id=project_id).update(phase='thumbnails_done')
        _emit_job_event(project_id, {'event': 'job.update', 'data': {
            'jobId': job_id, 'type': 'thumbnail', 'status': 'done',
        }})

    except Exception as exc:
        try:
            job = JobModel.objects.get(id=job_id)
            job.status = 'failed'
            job.error = str(exc)
            job.logs = logs
            job.save(update_fields=['status', 'error', 'logs', 'updated_at'])
            _emit_job_event(project_id, {'event': 'job.update', 'data': {
                'jobId': job_id, 'type': 'thumbnail', 'status': 'failed', 'error': str(exc),
            }})
        except Exception:
            pass


def thumbnail_generate(request, project_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    from studio.models import JobModel
    project_obj = _project_obj_or_404(request, project_id)

    job = JobModel.objects.create(
        project=project_obj,
        job_type='thumbnail',
        status='pending',
    )
    threading.Thread(
        target=_run_thumbnail_job,
        args=(str(job.id), project_id, project_obj.name),
        daemon=True,
    ).start()

    pd = _get_or_404(project_id, request.user)
    return render(request, 'thumbnail/_running.html', {
        'project': pd,
        'job': _job_display(job),
    })


def thumbnail_status(request, project_id):
    _project_obj_or_404(request, project_id)
    template, ctx = _thumbnail_template_and_ctx(project_id)
    return render(request, template, ctx)


def thumbnail_select(request, project_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    _project_obj_or_404(request, project_id)

    from studio.models import ThumbnailModel
    variant = request.POST.get('variant', '').strip().upper()
    if variant not in ('A', 'B', 'C'):
        return JsonResponse({'error': 'Variante inválida'}, status=400)

    ThumbnailModel.objects.filter(project_id=project_id).update(selected=False)
    ThumbnailModel.objects.filter(project_id=project_id, variant=variant).update(selected=True)

    template, ctx = _thumbnail_template_and_ctx(project_id)
    return render(request, template, ctx)


def thumbnail_image(request, project_id, variant):
    _project_obj_or_404(request, project_id)
    from django.http import FileResponse, HttpResponseRedirect
    variant = variant.upper()
    if variant not in ('A', 'B', 'C'):
        raise Http404
    storage = get_storage()
    key = f'studio/{project_id}/thumbnails/{variant}.jpg'
    if not storage.object_exists(key):
        raise Http404
    if storage.is_local:
        return FileResponse(open(storage.resolve_read_path(key), 'rb'), content_type='image/jpeg')
    return HttpResponseRedirect(storage.get_presigned_url(key, expires=300))


def _get_seo(project_id):
    from studio.models import SeoMetadataModel
    try:
        return SeoMetadataModel.objects.get(project_id=project_id)
    except SeoMetadataModel.DoesNotExist:
        return None


def _seo_display(seo) -> dict:
    tags = seo.tags or []
    return {
        'title':       seo.title,
        'description': seo.description,
        'tags':        tags,
        'tags_json':   json.dumps(tags, ensure_ascii=False),
        'approved':    seo.approved,
        'context':     seo.context,
        'tags_count':  len(tags),
        'tags_chars':  sum(len(t) for t in tags),
    }


def _latest_seo_job(project_id):
    from studio.models import JobModel
    return (
        JobModel.objects
        .filter(project_id=project_id, job_type='seo')
        .order_by('-created_at')
        .first()
    )


def _seo_template_and_ctx(project_id: str) -> tuple[str, dict]:
    pd = _get_or_404(project_id)
    job = _latest_seo_job(project_id)
    seo = _get_seo(project_id)

    if job and job.status == 'running':
        return 'seo/_running.html', {'project': pd, 'job': _job_display(job)}

    if seo:
        return 'seo/_editor.html', {'project': pd, 'seo': _seo_display(seo)}

    return 'seo/_generator.html', {
        'project': pd,
        'job_error': job.error if job and job.status == 'failed' else None,
    }


def seo_step(request, project_id):
    _project_obj_or_404(request, project_id)
    template, extra = _seo_template_and_ctx(project_id)
    pd = extra['project']
    if request.htmx:
        return render(request, template, extra)
    ctx = _step_ctx(pd, 'seo', {**extra, 'active_template': template})
    return render(request, 'projects/detail.html', ctx)


def _simulated_seo(project_name: str, channel_name: str, context: str) -> dict:
    name = project_name.strip()
    channel = channel_name.strip() or 'YouTube'
    ctx_line = f' — {context[:80]}' if context.strip() else ''
    title = f'{name[:85]}{ctx_line}'[:100]
    description = (
        f'Neste vídeo, {name.lower()}.{(" " + context.strip()) if context.strip() else ""}\n\n'
        '📌 O que você vai ver:\n'
        '→ Introdução ao tema\n'
        '→ Desenvolvimento passo a passo\n'
        '→ Resultado final e conclusão\n\n'
        f'Curtiu? Inscreva-se no canal {channel} e ative as notificações! '
        'Deixe seu comentário abaixo com dúvidas ou sugestões.\n\n'
        '#brasil #youtube #conteudo'
    )
    words = (name + ' ' + context).lower().split()
    base_tags = list(dict.fromkeys(w.strip('.,!?') for w in words if len(w) > 3))[:8]
    extra_tags = ['youtube', 'brasil', 'tutorial', 'dicas', 'vlog', channel.lower()]
    tags = (base_tags + extra_tags)[:15]
    return {'title': title, 'description': description, 'tags': tags}


def _run_seo_job(job_id: str, project_id: str, project_name: str,
                 channel_name: str, context: str) -> None:
    from studio.models import JobModel, SeoMetadataModel, ProjectModel
    try:
        job = JobModel.objects.get(id=job_id)
        job.status = 'running'
        job.save(update_fields=['status', 'updated_at'])
        _emit_job_event(project_id, {'event': 'job.update', 'data': {
            'jobId': job_id, 'type': 'seo', 'status': 'running',
        }})

        simulate = getattr(settings, 'SEO_SIMULATE', True)
        if simulate:
            _emit_job_event(project_id, {'event': 'job.update', 'data': {
                'jobId': job_id, 'type': 'seo', 'status': 'running',
                'log_line': '[SIMULADO] Gerando metadados SEO sem Claude…',
            }})
            data = _simulated_seo(project_name, channel_name, context)
        else:
            api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
            _emit_job_event(project_id, {'event': 'job.update', 'data': {
                'jobId': job_id, 'type': 'seo', 'status': 'running',
                'log_line': 'Chamando Claude para gerar título, descrição e tags…',
            }})
            from infrastructure.ai.seo_generator import generate_seo
            data = generate_seo(project_name, channel_name, context, api_key=api_key)

        title       = data.get('title', '')[:100]
        description = data.get('description', '')[:5000]
        tags        = [str(t)[:100] for t in data.get('tags', []) if t][:20]

        SeoMetadataModel.objects.update_or_create(
            project_id=project_id,
            defaults={
                'title':       title,
                'description': description,
                'tags':        tags,
                'approved':    False,
                'context':     context,
            },
        )

        job.status = 'done'
        job.result = {'title': title, 'tags_count': len(tags)}
        job.save(update_fields=['status', 'result', 'updated_at'])
        _emit_job_event(project_id, {'event': 'job.update', 'data': {
            'jobId': job_id, 'type': 'seo', 'status': 'done',
            'output_params': {'title': title, 'tags_count': len(tags)},
        }})

    except Exception as exc:
        try:
            job = JobModel.objects.get(id=job_id)
            job.status = 'failed'
            job.error = str(exc)
            job.save(update_fields=['status', 'error', 'updated_at'])
            _emit_job_event(project_id, {'event': 'job.update', 'data': {
                'jobId': job_id, 'type': 'seo', 'status': 'failed', 'error': str(exc),
            }})
        except Exception:
            pass


def seo_generate(request, project_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    _project_obj_or_404(request, project_id)

    from studio.models import JobModel
    project_obj = _project_obj_or_404(request, project_id)

    context = request.POST.get('context', '').strip()

    job = JobModel.objects.create(project=project_obj, job_type='seo', status='pending')
    threading.Thread(
        target=_run_seo_job,
        args=(str(job.id), project_id, project_obj.name, project_obj.channel_name, context),
        daemon=True,
    ).start()

    pd = _get_or_404(project_id, request.user)
    return render(request, 'seo/_running.html', {'project': pd, 'job': _job_display(job)})


def seo_status(request, project_id):
    _project_obj_or_404(request, project_id)
    template, ctx = _seo_template_and_ctx(project_id)
    return render(request, template, ctx)


def seo_save(request, project_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    _project_obj_or_404(request, project_id)

    from studio.models import SeoMetadataModel
    seo, _ = SeoMetadataModel.objects.get_or_create(project_id=project_id)

    title       = request.POST.get('title', seo.title)[:100]
    description = request.POST.get('description', seo.description)[:5000]
    raw_tags    = request.POST.get('tags', '[]')
    try:
        tags = [str(t)[:100] for t in json.loads(raw_tags) if t][:20]
    except (json.JSONDecodeError, ValueError):
        tags = seo.tags

    seo.title       = title
    seo.description = description
    seo.tags        = tags
    seo.approved    = False
    seo.save(update_fields=['title', 'description', 'tags', 'approved', 'updated_at'])

    pd = _get_or_404(project_id, request.user)
    return render(request, 'seo/_editor.html', {'project': pd, 'seo': _seo_display(seo)})


def seo_approve(request, project_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    _project_obj_or_404(request, project_id)

    from studio.models import SeoMetadataModel, ProjectModel
    seo = _get_seo(project_id)
    if not seo:
        return JsonResponse({'error': 'SEO não gerado ainda'}, status=400)

    seo.approved = True
    seo.save(update_fields=['approved', 'updated_at'])
    ProjectModel.objects.filter(id=project_id).update(phase='seo_approved')

    pd = _get_or_404(project_id, request.user)
    return render(request, 'seo/_editor.html', {'project': pd, 'seo': _seo_display(seo)})


# ── F07: YouTube Publish ───────────────────────────────────────

def _get_publish_record(project_id):
    from studio.models import PublishRecord
    try:
        return PublishRecord.objects.get(project_id=project_id)
    except PublishRecord.DoesNotExist:
        return None


def _latest_publish_job(project_id):
    from studio.models import JobModel
    return (
        JobModel.objects
        .filter(project_id=project_id, job_type='publish')
        .order_by('-created_at')
        .first()
    )


def _publish_checklist(project_id: str) -> tuple[list[dict], bool]:
    from studio.models import ProjectModel, SeoMetadataModel, ThumbnailModel
    items = []

    # Export done
    storage = get_storage()
    final_key = f'studio/{project_id}/final/final.mp4'
    export_ok = storage.object_exists(final_key)
    if export_ok:
        if storage.is_local:
            sz = os.path.getsize(storage.resolve_read_path(final_key))
            sz_str = f'{sz // (1024*1024)} MB' if sz >= 1024 * 1024 else f'{sz // 1024} KB'
        else:
            sz_str = 'disponível'
        export_label = f'Export concluído — {sz_str}'
    else:
        export_label = 'Export concluído'
    items.append({'ok': export_ok, 'label': export_label})

    # SEO approved
    try:
        seo = SeoMetadataModel.objects.get(project_id=project_id)
        seo_ok = seo.approved
        seo_label = f'SEO aprovado — "{seo.title[:40]}"' if seo.approved and seo.title else 'SEO aprovado'
    except SeoMetadataModel.DoesNotExist:
        seo_ok = False
        seo_label = 'SEO aprovado'
    items.append({'ok': seo_ok, 'label': seo_label})

    # Thumbnail selected
    thumb = ThumbnailModel.objects.filter(project_id=project_id, selected=True).first()
    thumb_ok = thumb is not None
    thumb_label = f'Thumbnail selecionada — Variante {thumb.variant}' if thumb else 'Thumbnail selecionada'
    items.append({'ok': thumb_ok, 'label': thumb_label})

    # YouTube connected
    try:
        proj = ProjectModel.objects.get(id=project_id)
        oauth_ok = bool(proj.oauth_refresh_token_enc)
    except ProjectModel.DoesNotExist:
        oauth_ok = False
    items.append({'ok': oauth_ok, 'label': 'Canal YouTube conectado'})

    return items, all(i['ok'] for i in items)


def _final_video_available(project_id: str) -> bool:
    return get_storage().object_exists(f'studio/{project_id}/final/final.mp4')


def _publish_template_and_ctx(project_id: str) -> tuple[str, dict]:
    pd = _get_or_404(project_id)
    job = _latest_publish_job(project_id)
    video_available = _final_video_available(project_id)

    if job and job.status == 'running':
        return 'publish/_running.html', {'project': pd, 'job': _job_display(job)}

    record = _get_publish_record(project_id)
    if record:
        return 'publish/_result.html', {
            'project':         pd,
            'record':          record,
            'pipeline_steps':  ['Fontes', 'Merge', 'Export', 'Thumbnails', 'SEO', 'Publicado'],
            'video_available': video_available,
        }

    checklist, all_ok = _publish_checklist(project_id)
    from studio.models import ProjectModel as _PM
    try:
        _proj = _PM.objects.get(id=project_id)
        oauth_connected = bool(_proj.oauth_refresh_token_enc)
    except _PM.DoesNotExist:
        oauth_connected = False
    return 'publish/_oauth.html', {
        'project':         pd,
        'checklist':       checklist,
        'all_ok':          all_ok,
        'oauth_connected': oauth_connected,
        'job_error':       job.error if job and job.status == 'failed' else None,
        'video_available': video_available,
    }


def publish_step(request, project_id):
    _project_obj_or_404(request, project_id)
    template, extra = _publish_template_and_ctx(project_id)
    pd = extra['project']
    if request.htmx:
        return render(request, template, extra)
    ctx = _step_ctx(pd, 'publish', {**extra, 'active_template': template})
    return render(request, 'projects/detail.html', ctx)


def publish_oauth_connect(request, project_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    project_obj = _project_obj_or_404(request, project_id)

    simulate = getattr(settings, 'PUBLISH_SIMULATE', True)
    if simulate:
        project_obj.oauth_refresh_token_enc = 'SIMULATED_TOKEN_PHASE0'
        project_obj.save(update_fields=['oauth_refresh_token_enc'])
    else:
        pre_token = getattr(settings, 'YOUTUBE_REFRESH_TOKEN', '')
        if pre_token:
            # Dev mode: token pré-configurado no .env.local — sem redirect OAuth
            from infrastructure.youtube.oauth import encode_token
            project_obj.oauth_refresh_token_enc = encode_token(pre_token)
            project_obj.save(update_fields=['oauth_refresh_token_enc'])
        else:
            # Web OAuth flow (credential tipo "web" no Google Cloud Console)
            from django.http import HttpResponseRedirect
            from google_auth_oauthlib.flow import Flow
            flow = Flow.from_client_config(
                {'web': {
                    'client_id':     settings.GOOGLE_CLIENT_ID,
                    'client_secret': settings.GOOGLE_CLIENT_SECRET,
                    'auth_uri':      'https://accounts.google.com/o/oauth2/auth',
                    'token_uri':     'https://oauth2.googleapis.com/token',
                    'redirect_uris': [request.build_absolute_uri(
                        f'/projects/{project_id}/publish/oauth/callback/'
                    )],
                }},
                scopes=['https://www.googleapis.com/auth/youtube.upload'],
            )
            flow.redirect_uri = request.build_absolute_uri(
                f'/projects/{project_id}/publish/oauth/callback/'
            )
            auth_url, state = flow.authorization_url(
                access_type='offline', include_granted_scopes='true', prompt='consent'
            )
            request.session[f'oauth_state_{project_id}'] = state
            return HttpResponseRedirect(auth_url)

    template, ctx = _publish_template_and_ctx(project_id)
    return render(request, template, ctx)


def publish_oauth_callback(request, project_id):
    """Callback do Google OAuth — troca code por refresh_token."""
    _project_obj_or_404(request, project_id)
    from django.http import HttpResponseRedirect
    from google_auth_oauthlib.flow import Flow
    from infrastructure.youtube.oauth import encode_token

    state = request.session.get(f'oauth_state_{project_id}', '')
    flow = Flow.from_client_config(
        {'web': {
            'client_id':     settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'auth_uri':      'https://accounts.google.com/o/oauth2/auth',
            'token_uri':     'https://oauth2.googleapis.com/token',
            'redirect_uris': [request.build_absolute_uri(
                f'/projects/{project_id}/publish/oauth/callback/'
            )],
        }},
        scopes=['https://www.googleapis.com/auth/youtube.upload'],
        state=state,
    )
    flow.redirect_uri = request.build_absolute_uri(
        f'/projects/{project_id}/publish/oauth/callback/'
    )
    flow.fetch_token(authorization_response=request.build_absolute_uri(request.get_full_path()))

    from studio.models import ProjectModel
    ProjectModel.objects.filter(id=project_id).update(
        oauth_refresh_token_enc=encode_token(flow.credentials.refresh_token)
    )
    del request.session[f'oauth_state_{project_id}']
    return HttpResponseRedirect(f'/projects/{project_id}/publish/')


def publish_oauth_disconnect(request, project_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    project_obj = _project_obj_or_404(request, project_id)

    project_obj.oauth_refresh_token_enc = ''
    project_obj.save(update_fields=['oauth_refresh_token_enc'])

    template, ctx = _publish_template_and_ctx(project_id)
    return render(request, template, ctx)


def _run_publish_job(job_id: str, project_id: str, visibility: str) -> None:
    from studio.models import JobModel, ProjectModel, PublishRecord
    logs = []
    try:
        job = JobModel.objects.get(id=job_id)
        job.status = 'running'
        job.save(update_fields=['status', 'updated_at'])
        _emit_job_event(project_id, {'event': 'job.update', 'data': {
            'jobId': job_id, 'type': 'publish', 'status': 'running',
        }})

        simulate = getattr(settings, 'PUBLISH_SIMULATE', True)
        if simulate:
            _emit_job_event(project_id, {'event': 'job.update', 'data': {
                'jobId': job_id, 'type': 'publish', 'status': 'running',
                'log_line': '[SIMULADO] Iniciando upload para YouTube…',
            }})
            time.sleep(0.8)
            _emit_job_event(project_id, {'event': 'job.update', 'data': {
                'jobId': job_id, 'type': 'publish', 'status': 'running',
                'log_line': '[SIMULADO] Upload em progresso (100%)…',
            }})
            time.sleep(0.7)
            video_id    = 'dQw4w9WgXcQ'
            youtube_url = f'https://www.youtube.com/watch?v={video_id}'
            logs.append({'text': '[SIMULADO] Upload para YouTube simulado', 'type': 'info'})
            logs.append({'text': f'video_id fictício: {video_id}', 'type': 'success'})
        else:
            from studio.models import SeoMetadataModel
            project_obj = ProjectModel.objects.get(id=project_id)
            final_key   = f'studio/{project_id}/final/final.mp4'
            final_path  = get_storage().resolve_read_path(final_key)
            # Usa SEO aprovado se disponível
            seo = SeoMetadataModel.objects.filter(project_id=project_id).first()
            title       = (seo.title       if seo and seo.title       else project_obj.name)
            description = (seo.description if seo and seo.description else '')
            tags        = (seo.tags        if seo and seo.tags        else [])
            from infrastructure.youtube.uploader import upload_video
            video_id = upload_video(
                refresh_token_enc=project_obj.oauth_refresh_token_enc,
                video_path=final_path,
                title=title,
                description=description,
                tags=tags,
                visibility=visibility,
                log_fn=lambda msg: logs.append({'text': msg, 'type': 'info'}),
            )
            youtube_url = f'https://www.youtube.com/watch?v={video_id}'
            logs.append({'text': f'Upload concluído: {youtube_url}', 'type': 'success'})

        PublishRecord.objects.update_or_create(
            project_id=project_id,
            defaults={'video_id': video_id, 'youtube_url': youtube_url, 'visibility': visibility},
        )

        job.status = 'done'
        job.logs   = logs
        job.result = {'video_id': video_id, 'youtube_url': youtube_url}
        job.save(update_fields=['status', 'logs', 'result', 'updated_at'])
        ProjectModel.objects.filter(id=project_id).update(phase='published')
        _emit_job_event(project_id, {'event': 'job.update', 'data': {
            'jobId': job_id, 'type': 'publish', 'status': 'done',
            'output_params': {'video_id': video_id, 'youtube_url': youtube_url},
        }})

    except Exception as exc:
        try:
            job = JobModel.objects.get(id=job_id)
            job.status = 'failed'
            job.error  = str(exc)
            job.logs   = logs
            job.save(update_fields=['status', 'error', 'logs', 'updated_at'])
            _emit_job_event(project_id, {'event': 'job.update', 'data': {
                'jobId': job_id, 'type': 'publish', 'status': 'failed', 'error': str(exc),
            }})
        except Exception:
            pass


def publish_start(request, project_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    from studio.models import JobModel
    project_obj = _project_obj_or_404(request, project_id)

    visibility = request.POST.get('visibility', 'private')
    if visibility not in ('public', 'unlisted', 'private'):
        visibility = 'private'

    job = JobModel.objects.create(project=project_obj, job_type='publish', status='pending')
    threading.Thread(
        target=_run_publish_job,
        args=(str(job.id), project_id, visibility),
        daemon=True,
    ).start()

    pd = _get_or_404(project_id, request.user)
    return render(request, 'publish/_running.html', {'project': pd, 'job': _job_display(job)})


def publish_status(request, project_id):
    _project_obj_or_404(request, project_id)
    template, ctx = _publish_template_and_ctx(project_id)
    return render(request, template, ctx)

# ── F02: Source upload / delete / list ────────────────────────

def upload_source(request, project_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    _project_obj_or_404(request, project_id)

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

    # Salvar arquivo via storage port
    storage_key = f"studio/{project_id}/sources/{source_id}-{file.name}"
    storage = get_storage()
    storage.put_object(storage_key, file.read(), f'video/{ext}')

    # Tentar extrair duração via ffprobe
    try:
        duration_sec = _probe_duration(storage.resolve_read_path(storage_key))
    except Exception:
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


def source_preview(request, project_id, source_id):
    """F18 — stream inline do vídeo de origem (não o highlight cortado), para
    o player do editor de timeline."""
    _project_obj_or_404(request, project_id)
    from django.http import FileResponse, HttpResponseRedirect
    from studio.models import SourceModel
    try:
        source = SourceModel.objects.get(id=source_id, project_id=project_id)
    except SourceModel.DoesNotExist:
        raise Http404
    storage = get_storage()
    if storage.is_local:
        return FileResponse(
            open(storage.resolve_read_path(source.storage_key), 'rb'),
            content_type='video/mp4',
        )
    return HttpResponseRedirect(storage.get_presigned_url(source.storage_key, expires=3600))


def delete_source(request, project_id, source_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    _project_obj_or_404(request, project_id)

    from studio.models import SourceModel
    try:
        source = SourceModel.objects.get(id=source_id, project_id=project_id)
    except SourceModel.DoesNotExist:
        return JsonResponse({'error': 'Source não encontrado'}, status=404)

    # Deletar arquivo do storage
    if source.storage_key:
        try:
            get_storage().delete_object(source.storage_key)
        except Exception:
            pass

    source.delete()

    # Retornar lista atualizada (HTMX swap)
    pd = _get_or_404(project_id)
    sources = _list_sources_display(project_id)
    return render(request, 'sources/_source_list.html', {'project': pd, 'sources': sources})


def source_list_partial(request, project_id):
    _project_obj_or_404(request, project_id)
    pd = _get_or_404(project_id)
    sources = _list_sources_display(project_id)
    return render(request, 'sources/_source_list.html', {'project': pd, 'sources': sources})


def health_check(request):
    return JsonResponse({'status': 'ok'})


# ── F09: REST API — jobs ───────────────────────────────────────

def api_job_list(request, project_id):
    """GET /api/projects/:id/jobs/ — últimos 20 jobs do projeto."""
    from studio.models import JobModel
    _project_obj_or_404(request, project_id)
    jobs = JobModel.objects.filter(project_id=project_id).order_by('-created_at')[:20]
    return JsonResponse({
        'jobs': [
            {
                'id':         str(j.id),
                'job_type':   j.job_type,
                'status':     j.status,
                'error':      j.error,
                'result':     j.result,
                'created_at': j.created_at.isoformat() if j.created_at else None,
                'updated_at': j.updated_at.isoformat() if j.updated_at else None,
            }
            for j in jobs
        ]
    })


def api_job_detail(request, project_id, job_id):
    """GET /api/projects/:id/jobs/:jobId — job com logs completos."""
    from studio.models import JobModel
    _project_obj_or_404(request, project_id)
    try:
        job = JobModel.objects.get(id=job_id, project_id=project_id)
    except JobModel.DoesNotExist:
        raise Http404
    return JsonResponse({
        'id':         str(job.id),
        'job_type':   job.job_type,
        'status':     job.status,
        'error':      job.error,
        'logs':       job.logs or [],
        'result':     job.result or {},
        'created_at': job.created_at.isoformat() if job.created_at else None,
        'updated_at': job.updated_at.isoformat() if job.updated_at else None,
    })


# ── F17: REST API — highlights ──────────────────────────────────

def api_highlight_detect(request, project_id):
    """POST /api/projects/:id/jobs/highlight-detect — ver api-contracts.md."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    project_obj = _project_obj_or_404(request, project_id)

    try:
        job = _launch_highlight_job(project_obj)
    except HighlightDetectError as exc:
        return JsonResponse({'detail': exc.message}, status=exc.status)

    return JsonResponse({'job_id': str(job.id), 'status': job.status}, status=202)


def api_highlight_list(request, project_id):
    """GET /api/projects/:id/highlights — ver api-contracts.md."""
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])
    _project_obj_or_404(request, project_id)
    return JsonResponse(_list_highlight_moments(project_id), safe=False)


def api_highlight_update(request, project_id, highlight_id):
    """PATCH /api/projects/:id/highlights/:highlightId — ver api-contracts.md."""
    if request.method != 'PATCH':
        return HttpResponseNotAllowed(['PATCH'])
    _project_obj_or_404(request, project_id)

    from studio.models import HighlightMomentModel
    try:
        moment = HighlightMomentModel.objects.get(id=highlight_id, project_id=project_id)
    except HighlightMomentModel.DoesNotExist:
        raise Http404

    try:
        payload = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'invalid JSON body'}, status=400)

    if 'included' in payload:
        moment.included = bool(payload['included'])
        moment.save(update_fields=['included'])

    return JsonResponse({
        'id':            str(moment.id),
        'source_id':     str(moment.source_id) if moment.source_id else None,
        'timestamp_sec': moment.timestamp_sec,
        'tipo':          moment.tipo,
        'descricao':     moment.descricao,
        'importancia':   moment.importancia,
        'included':      moment.included,
    })
