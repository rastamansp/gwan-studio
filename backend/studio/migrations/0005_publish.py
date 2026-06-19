import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('studio', '0004_seo'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectmodel',
            name='oauth_refresh_token_enc',
            field=models.CharField(blank=True, default='', max_length=512),
            preserve_default=False,
        ),
        migrations.CreateModel(
            name='PublishRecord',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('video_id', models.CharField(max_length=50)),
                ('youtube_url', models.CharField(max_length=200)),
                ('visibility', models.CharField(default='private', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('project', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='publish',
                    to='studio.projectmodel',
                )),
            ],
            options={'db_table': 'studio_publish'},
        ),
    ]
