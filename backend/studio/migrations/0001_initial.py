import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name='ProjectModel',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('channel_name', models.CharField(blank=True, max_length=100)),
                ('phase', models.CharField(
                    choices=[
                        ('new', 'Novo'),
                        ('sources_uploaded', 'Fontes Enviadas'),
                        ('merge_done', 'Merge Concluído'),
                        ('export_done', 'Export Pronto'),
                        ('thumbnails_done', 'Thumbnails OK'),
                        ('seo_approved', 'SEO Aprovado'),
                    ],
                    default='new',
                    max_length=30,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['-updated_at'], 'db_table': 'studio_project'},
        ),
        migrations.CreateModel(
            name='SourceModel',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='sources',
                    to='studio.projectmodel',
                )),
                ('original_filename', models.CharField(max_length=255)),
                ('camera', models.CharField(blank=True, max_length=100)),
                ('duration_sec', models.IntegerField(default=0)),
                ('size_bytes', models.BigIntegerField(default=0)),
                ('status', models.CharField(
                    choices=[
                        ('uploading', 'Enviando'),
                        ('ready', 'Pronto'),
                        ('error', 'Erro'),
                    ],
                    default='uploading',
                    max_length=20,
                )),
                ('storage_key', models.CharField(blank=True, max_length=512)),
                ('sort_order', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['sort_order', 'created_at'], 'db_table': 'studio_source'},
        ),
    ]
