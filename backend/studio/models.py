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
