import uuid
from django.conf import settings
from django.db import models


DEFAULT_HIGHLIGHT_SETTINGS = {
    'pre_roll': 6.0,
    'post_roll': 8.0,
    'merge_gap': 4.0,
    'top_n_peaks': 40,
    'importancia_min': 5,
}


class ProjectModel(models.Model):
    class Phase(models.TextChoices):
        NEW = 'new', 'Novo'
        SOURCES_UPLOADED = 'sources_uploaded', 'Fontes Enviadas'
        MERGE_DONE = 'merge_done', 'Merge Concluído'
        HIGHLIGHTS_DONE = 'highlights_done', 'Highlights Detectados'
        EXPORT_DONE = 'export_done', 'Export Pronto'
        THUMBNAILS_DONE = 'thumbnails_done', 'Thumbnails OK'
        SEO_APPROVED = 'seo_approved', 'SEO Aprovado'
        PUBLISHED    = 'published',   'Publicado'

    class ProjectType(models.TextChoices):
        GOPRO   = 'gopro',   'Go Pro'
        FUTEBOL = 'futebol', 'Futebol'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='studio_projects',
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255)
    channel_name = models.CharField(max_length=100, blank=True)
    project_type = models.CharField(
        max_length=20, choices=ProjectType.choices, default=ProjectType.GOPRO,
    )
    highlight_settings = models.JSONField(default=dict, blank=True)
    phase = models.CharField(max_length=30, choices=Phase.choices, default=Phase.NEW)
    oauth_refresh_token_enc = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        db_table = 'studio_project'

    def __str__(self):
        return self.name


class SourceModel(models.Model):
    class Status(models.TextChoices):
        UPLOADING = 'uploading', 'Enviando'
        READY = 'ready', 'Pronto'
        ERROR = 'error', 'Erro'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(ProjectModel, on_delete=models.CASCADE, related_name='sources')
    original_filename = models.CharField(max_length=255)
    camera = models.CharField(max_length=100, blank=True)
    duration_sec = models.IntegerField(default=0)
    size_bytes = models.BigIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPLOADING)
    storage_key = models.CharField(max_length=512, blank=True)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'created_at']
        db_table = 'studio_source'


class HighlightMomentModel(models.Model):
    """F17 — momento relevante detectado no pipeline de futebol."""

    class Tipo(models.TextChoices):
        GOL       = 'gol',       'Gol'
        DEFESA    = 'defesa',    'Defesa'
        PENALTI   = 'penalti',   'Pênalti'
        FALTA     = 'falta',     'Falta'
        EXPULSAO  = 'expulsao',  'Expulsão'
        CHANCE    = 'chance',    'Chance'
        OUTRO     = 'outro',     'Outro'

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project       = models.ForeignKey(ProjectModel, on_delete=models.CASCADE, related_name='highlight_moments')
    source        = models.ForeignKey(
        'SourceModel', on_delete=models.CASCADE, related_name='highlight_moments',
        null=True, blank=True,
    )
    timestamp_sec = models.FloatField()
    tipo          = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.OUTRO)
    descricao     = models.TextField(blank=True)
    importancia   = models.IntegerField(default=0)
    included      = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp_sec']
        db_table = 'studio_highlight_moment'

    def __str__(self):
        return f"[{self.tipo}] {self.timestamp_sec:.0f}s — {self.project}"


class HighlightClipModel(models.Model):
    """F18 — plano de corte persistido (EDL), editável no editor de timeline."""

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project    = models.ForeignKey(ProjectModel, on_delete=models.CASCADE, related_name='highlight_clips')
    source     = models.ForeignKey('SourceModel', on_delete=models.CASCADE, related_name='highlight_clips')
    start_sec  = models.FloatField()
    end_sec    = models.FloatField()
    order      = models.IntegerField(default=0)
    included   = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        db_table = 'studio_highlight_clip'

    def __str__(self):
        return f"clip {self.start_sec:.1f}s-{self.end_sec:.1f}s — {self.project}"


class JobModel(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Aguardando'
        RUNNING = 'running', 'Executando'
        DONE    = 'done',    'Concluído'
        FAILED  = 'failed',  'Falhou'

    class JobType(models.TextChoices):
        MERGE             = 'merge',             'Merge'
        HIGHLIGHT_DETECT  = 'highlight_detect',  'Detecção de Highlights'
        EXPORT            = 'export',            'Export'
        THUMBNAIL         = 'thumbnail',         'Thumbnail'
        SEO               = 'seo',               'SEO'
        PUBLISH           = 'publish',            'Publicar'

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project      = models.ForeignKey(ProjectModel, on_delete=models.CASCADE, related_name='jobs')
    job_type     = models.CharField(max_length=20, choices=JobType.choices)
    status       = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    logs         = models.JSONField(default=list)
    result       = models.JSONField(null=True, blank=True)
    error        = models.TextField(blank=True)
    source_order = models.JSONField(default=list)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'studio_job'

    def __str__(self):
        return f"{self.job_type} [{self.status}] — {self.project}"


class ThumbnailModel(models.Model):
    class Variant(models.TextChoices):
        A = 'A', 'Variante A'
        B = 'B', 'Variante B'
        C = 'C', 'Variante C'

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project    = models.ForeignKey(ProjectModel, on_delete=models.CASCADE, related_name='thumbnails')
    variant    = models.CharField(max_length=1, choices=Variant.choices)
    plan       = models.JSONField(default=dict)
    output_key = models.CharField(max_length=512, blank=True)
    selected   = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('project', 'variant')]
        ordering = ['variant']
        db_table = 'studio_thumbnail'

    def __str__(self):
        return f"Thumbnail {self.variant} — {self.project}"


class SeoMetadataModel(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project     = models.OneToOneField(ProjectModel, on_delete=models.CASCADE, related_name='seo')
    title       = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    tags        = models.JSONField(default=list)
    approved    = models.BooleanField(default=False)
    context     = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'studio_seo'

    def __str__(self):
        return f"SEO — {self.project}"


class PublishRecord(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project     = models.OneToOneField(ProjectModel, on_delete=models.CASCADE, related_name='publish')
    video_id    = models.CharField(max_length=50)
    youtube_url = models.CharField(max_length=200)
    visibility  = models.CharField(max_length=20, default='private')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'studio_publish'

    def __str__(self):
        return f"Publish {self.video_id} — {self.project}"
