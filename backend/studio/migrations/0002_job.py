import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='JobModel',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='jobs',
                    to='studio.projectmodel',
                )),
                ('job_type', models.CharField(
                    choices=[
                        ('merge', 'Merge'),
                        ('export', 'Export'),
                        ('thumbnail', 'Thumbnail'),
                        ('seo', 'SEO'),
                        ('publish', 'Publicar'),
                    ],
                    max_length=20,
                )),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Aguardando'),
                        ('running', 'Executando'),
                        ('done', 'Concluído'),
                        ('failed', 'Falhou'),
                    ],
                    default='pending',
                    max_length=20,
                )),
                ('logs', models.JSONField(default=list)),
                ('result', models.JSONField(blank=True, null=True)),
                ('error', models.TextField(blank=True)),
                ('source_order', models.JSONField(default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['-created_at'], 'db_table': 'studio_job'},
        ),
    ]
