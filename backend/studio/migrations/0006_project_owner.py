from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def assign_existing_projects(apps, schema_editor):
    ProjectModel = apps.get_model('studio', 'ProjectModel')
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))

    owner = User.objects.filter(is_superuser=True).order_by('id').first()
    if owner is None:
        owner = User.objects.order_by('id').first()

    if owner is None:
        return

    ProjectModel.objects.filter(owner__isnull=True).update(owner=owner)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('studio', '0005_publish'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectmodel',
            name='owner',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='studio_projects',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(assign_existing_projects, migrations.RunPython.noop),
    ]
