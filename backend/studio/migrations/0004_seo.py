import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0003_thumbnail'),
    ]

    operations = [
        migrations.CreateModel(
            name='SeoMetadataModel',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('project', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='seo',
                    to='studio.projectmodel',
                )),
                ('title',       models.CharField(blank=True, max_length=200)),
                ('description', models.TextField(blank=True)),
                ('tags',        models.JSONField(default=list)),
                ('approved',    models.BooleanField(default=False)),
                ('context',     models.TextField(blank=True)),
                ('created_at',  models.DateTimeField(auto_now_add=True)),
                ('updated_at',  models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'studio_seo'},
        ),
    ]
