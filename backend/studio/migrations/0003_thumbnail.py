import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0002_job'),
    ]

    operations = [
        migrations.CreateModel(
            name='ThumbnailModel',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='thumbnails',
                    to='studio.projectmodel',
                )),
                ('variant', models.CharField(
                    choices=[('A', 'Variante A'), ('B', 'Variante B'), ('C', 'Variante C')],
                    max_length=1,
                )),
                ('plan', models.JSONField(default=dict)),
                ('output_key', models.CharField(blank=True, max_length=512)),
                ('selected', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['variant'], 'db_table': 'studio_thumbnail'},
        ),
        migrations.AddConstraint(
            model_name='thumbnailmodel',
            constraint=models.UniqueConstraint(
                fields=['project', 'variant'],
                name='unique_project_variant',
            ),
        ),
    ]
