import uuid
from django.db import models


class ProjectModel(models.Model):
    class Phase(models.TextChoices):
        NEW = 'new', 'Novo'
        SOURCES_UPLOADED = 'sources_uploaded', 'Fontes Enviadas'
        MERGE_DONE = 'merge_done', 'Merge Concluído'
        EXPORT_DONE = 'export_done', 'Export Pronto'
        THUMBNAILS_DONE = 'thumbnails_done', 'Thumbnails OK'
        SEO_APPROVED = 'seo_approved', 'SEO Aprovado'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    channel_name = models.CharField(max_length=100, blank=True)
    phase = models.CharField(max_length=30, choices=Phase.choices, default=Phase.NEW)
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


class JobModel(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Aguardando'
        RUNNING = 'running', 'Executando'
        DONE    = 'done',    'Concluído'
        FAILED  = 'failed',  'Falhou'

    class JobType(models.TextChoices):
        MERGE     = 'merge',     'Merge'
        EXPORT    = 'export',    'Export'
        THUMBNAIL = 'thumbnail', 'Thumbnail'
        SEO       = 'seo',       'SEO'
        PUBLISH   = 'publish',   'Publicar'

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
