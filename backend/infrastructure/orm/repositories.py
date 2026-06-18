from domain.entities import Project, Source
from domain.ports import IProjectRepository, ISourceRepository


class DjangoProjectRepository(IProjectRepository):
    def save(self, project: Project) -> Project:
        from studio.models import ProjectModel
        obj, _ = ProjectModel.objects.update_or_create(
            id=project.id,
            defaults={
                'name': project.name,
                'channel_name': project.channel_name,
                'phase': project.phase,
            },
        )
        return _to_entity(obj)

    def get(self, project_id: str) -> Project:
        from studio.models import ProjectModel
        obj = ProjectModel.objects.get(id=project_id)
        return _to_entity(obj)

    def list(self) -> list[Project]:
        from studio.models import ProjectModel
        return [_to_entity(obj) for obj in ProjectModel.objects.all()]


class DjangoSourceRepository(ISourceRepository):
    def save(self, source: Source) -> Source:
        from studio.models import SourceModel, ProjectModel
        project = ProjectModel.objects.get(id=source.project_id)
        obj, _ = SourceModel.objects.update_or_create(
            id=source.id,
            defaults={
                'project': project,
                'original_filename': source.original_filename,
                'camera': source.camera,
                'duration_sec': source.duration_sec,
                'size_bytes': source.size_bytes,
                'status': source.status,
                'storage_key': source.storage_key or '',
            },
        )
        return _to_source_entity(obj)

    def get(self, source_id: str) -> Source:
        from studio.models import SourceModel
        obj = SourceModel.objects.get(id=source_id)
        return _to_source_entity(obj)

    def list_by_project(self, project_id: str) -> list[Source]:
        from studio.models import SourceModel
        return [_to_source_entity(obj) for obj in SourceModel.objects.filter(project_id=project_id)]

    def delete(self, source_id: str) -> None:
        from studio.models import SourceModel
        SourceModel.objects.filter(id=source_id).delete()


def _to_source_entity(obj) -> Source:
    return Source(
        id=str(obj.id),
        project_id=str(obj.project_id),
        original_filename=obj.original_filename,
        camera=obj.camera,
        duration_sec=obj.duration_sec,
        size_bytes=obj.size_bytes,
        status=obj.status,
        storage_key=obj.storage_key or None,
    )


def _to_entity(obj) -> Project:
    return Project(
        id=str(obj.id),
        name=obj.name,
        channel_name=obj.channel_name,
        phase=obj.phase,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )
