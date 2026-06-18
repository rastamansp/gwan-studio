from domain.entities import Project
from domain.ports import IProjectRepository


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


def _to_entity(obj) -> Project:
    return Project(
        id=str(obj.id),
        name=obj.name,
        channel_name=obj.channel_name,
        phase=obj.phase,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )
