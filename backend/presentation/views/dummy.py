"""
Fase 0 — views dummy com dados hardcoded.
Regra: zero ORM, zero serviços externos, zero lógica de negócio.
"""
from django.http import JsonResponse
from django.shortcuts import render

PHASE_LABELS = {
    "new":               ("Novo",              "neutral"),
    "sources_uploaded":  ("Fontes Enviadas",   "info"),
    "merge_done":        ("Merge Concluído",   "warning"),
    "export_done":       ("Export Pronto",     "warning"),
    "thumbnails_done":   ("Thumbnails OK",     "warning"),
    "seo_approved":      ("SEO Aprovado",      "success"),
}

MOCK_PROJECT = {
    "id":             "mock-001",
    "name":          "Pedalada 200km — Serra Gaúcha",
    "channel_name":  "@ramortinho",
    "phase":         "seo_approved",
    "phase_label":   "SEO Aprovado",
    "phase_color":   "success",
    "sources_count": 3,
    "total_duration": "20m 37s",
    "updated_at":    "Hoje, 14:32",
}

MOCK_PROJECTS = [
    {**MOCK_PROJECT},
    {
        "id":             "mock-002",
        "name":          "Gran Fondo — Serra da Mantiqueira",
        "channel_name":  "@ramortinho",
        "phase":         "merge_done",
        "phase_label":   "Merge Concluído",
        "phase_color":   "warning",
        "sources_count": 5,
        "total_duration": "45m 12s",
        "updated_at":    "Ontem, 09:15",
    },
    {
        "id":             "mock-003",
        "name":          "Trilha MTB — Florianópolis",
        "channel_name":  "@ramortinho",
        "phase":         "new",
        "phase_label":   "Novo",
        "phase_color":   "neutral",
        "sources_count": 0,
        "total_duration": "—",
        "updated_at":    "3 dias atrás",
    },
]

MOCK_SOURCES = [
    {
        "id": "s1",
        "original_filename": "GoPro_001.mp4",
        "camera":            "GoPro Hero 12",
        "duration_sec":      1234,
        "duration_fmt":      "20m 34s",
        "file_size_mb":      4.2,
        "status":            "ready",
    },
    {
        "id": "s2",
        "original_filename": "GoPro_002.mp4",
        "camera":            "GoPro Hero 12",
        "duration_sec":      987,
        "duration_fmt":      "16m 27s",
        "file_size_mb":      3.8,
        "status":            "ready",
    },
    {
        "id": "s3",
        "original_filename": "iPhone_001.mp4",
        "camera":            "iPhone 15 Pro",
        "duration_sec":      456,
        "duration_fmt":      "7m 36s",
        "file_size_mb":      2.1,
        "status":            "ready",
    },
]

MOCK_JOB_LOGS = [
    {"text": "[00:00] Iniciando merge de 3 fontes...", "type": "info"},
    {"text": "[00:02] ffmpeg: concat filter aplicado", "type": "info"},
    {"text": "[00:15] ffmpeg: processando 00:01:00 / 00:02:34", "type": "progress"},
    {"text": "[00:28] ffmpeg: processando 00:02:00 / 00:02:34", "type": "progress"},
    {"text": "[00:31] ffmpeg: concluído — merged.mp4 (287 MB)", "type": "success"},
    {"text": "[00:32] Upload para MinIO: studio/mock-001/merged.mp4 ✓", "type": "upload"},
]

MOCK_SEO = {
    "title": "Como eu pedalei 200 km em 3 dias pela Serra Gaúcha 🚴",
    "description": (
        "Nessa aventura incrível, pedalei 200 km em apenas 3 dias pela belíssima Serra Gaúcha, "
        "passando por vinícolas, paisagens de tirar o fôlego e subidas que testaram os meus limites.\n\n"
        "Roteiro completo, dicas de hospedagem e onde parar para comer no link da bio!\n\n"
        "⏱ Capítulos:\n"
        "00:00 - Introdução\n"
        "01:20 - Dia 1 - Saída de Caxias do Sul\n"
        "15:40 - Dia 2 - Vinícolas e descidas\n"
        "38:00 - Dia 3 - Chegada em Bento Gonçalves"
    ),
    "tags": ["ciclismo", "serra gaúcha", "cycling", "bike touring", "GoPro", "viagem de bike", "RS"],
}

MOCK_THUMBNAIL_VARIANTS = [
    {
        "id":          "A",
        "description": "Frame de subida dramática, expressão de esforço, overlay com distância",
        "gradient":    "from-orange-950 via-red-900 to-amber-800",
        "overlay_top": "🏔️ 200 KM",
        "overlay_sub": "Serra Gaúcha",
        "tag":         "Alta intensidade",
    },
    {
        "id":          "B",
        "description": "Vista panorâmica das vinícolas, sobreposição de rota no mapa",
        "gradient":    "from-emerald-950 via-green-900 to-teal-800",
        "overlay_top": "🍇 ROTA COMPLETA",
        "overlay_sub": "3 Dias de Pedal",
        "tag":         "Paisagem",
    },
    {
        "id":          "C",
        "description": "Selfie no topo, badge '200 km' em destaque, fundo desfocado",
        "gradient":    "from-blue-950 via-indigo-900 to-violet-800",
        "overlay_top": "🏆 COMPLETEI",
        "overlay_sub": "200 km em 3 dias",
        "tag":         "Conquista",
    },
]

PHASE_STEP_INDEX = {
    "new":              0,
    "sources_uploaded": 1,
    "merge_done":       2,
    "export_done":      3,
    "thumbnails_done":  4,
    "seo_approved":     5,
}

STEPS_META = [
    ("sources",   "Fontes"),
    ("merge",     "Merge"),
    ("export",    "Export"),
    ("thumbnail", "Thumbnails"),
    ("seo",       "SEO"),
    ("publish",   "Publicar"),
]


def _build_steps(project: dict, active_key: str) -> list[dict]:
    phase_idx = PHASE_STEP_INDEX.get(project["phase"], 0)
    result = []
    for i, (key, label) in enumerate(STEPS_META):
        result.append({
            "key":     key,
            "label":   label,
            "url":     f"/projects/{project['id']}/{key}/",
            "enabled": i <= phase_idx,
            "done":    i < phase_idx,
            "active":  key == active_key,
            "index":   i + 1,
        })
    return result


def _step_ctx(project, active_key, extra=None):
    steps = _build_steps(project, active_key)
    ctx = {
        "project":     project,
        "steps":       steps,
        "steps_done":  sum(1 for s in steps if s["done"]),
        "steps_total": len(steps),
        "active_step": active_key,
    }
    if extra:
        ctx.update(extra)
    return ctx


# ──────────────────────────── views ────────────────────────────

def project_list(request):
    return render(request, "projects/list.html", {"projects": MOCK_PROJECTS})


def project_new(request):
    return render(request, "projects/list.html", {"projects": MOCK_PROJECTS})


def project_detail(request, project_id):
    ctx = _step_ctx(MOCK_PROJECT, "sources", {"sources": MOCK_SOURCES,
                                               "active_template": "sources/_dropzone.html"})
    return render(request, "projects/detail.html", ctx)


def sources_step(request, project_id):
    extra = {"sources": MOCK_SOURCES}
    if request.htmx:
        return render(request, "sources/_dropzone.html", {"project": MOCK_PROJECT, **extra})
    ctx = _step_ctx(MOCK_PROJECT, "sources", {**extra, "active_template": "sources/_dropzone.html"})
    return render(request, "projects/detail.html", ctx)


def merge_step(request, project_id):
    extra = {"sources": MOCK_SOURCES, "job_logs": MOCK_JOB_LOGS}
    if request.htmx:
        return render(request, "merge/_editor.html", {"project": MOCK_PROJECT, **extra})
    ctx = _step_ctx(MOCK_PROJECT, "merge", {**extra, "active_template": "merge/_editor.html"})
    return render(request, "projects/detail.html", ctx)


def export_step(request, project_id):
    extra = {"job_logs": MOCK_JOB_LOGS}
    if request.htmx:
        return render(request, "export/_settings.html", {"project": MOCK_PROJECT, **extra})
    ctx = _step_ctx(MOCK_PROJECT, "export", {**extra, "active_template": "export/_settings.html"})
    return render(request, "projects/detail.html", ctx)


def thumbnail_step(request, project_id):
    extra = {"thumbnail_variants": MOCK_THUMBNAIL_VARIANTS}
    if request.htmx:
        return render(request, "thumbnail/_generator.html", {"project": MOCK_PROJECT, **extra})
    ctx = _step_ctx(MOCK_PROJECT, "thumbnail", {**extra, "active_template": "thumbnail/_generator.html"})
    return render(request, "projects/detail.html", ctx)


def seo_step(request, project_id):
    extra = {"seo": MOCK_SEO}
    if request.htmx:
        return render(request, "seo/_generator.html", {"project": MOCK_PROJECT, **extra})
    ctx = _step_ctx(MOCK_PROJECT, "seo", {**extra, "active_template": "seo/_generator.html"})
    return render(request, "projects/detail.html", ctx)


def publish_step(request, project_id):
    if request.htmx:
        return render(request, "publish/_oauth.html", {"project": MOCK_PROJECT})
    ctx = _step_ctx(MOCK_PROJECT, "publish", {"active_template": "publish/_oauth.html"})
    return render(request, "projects/detail.html", ctx)


def health_check(request):
    return JsonResponse({"status": "ok"})
