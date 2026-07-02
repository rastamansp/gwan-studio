import uuid
from domain.entities import DEFAULT_HIGHLIGHT_SETTINGS, Project
from domain.ports import IProjectRepository

VALID_PROJECT_TYPES = ('gopro', 'futebol')


class ListProjects:
    def __init__(self, repo: IProjectRepository):
        self.repo = repo

    def execute(self, project_type: str | None = None) -> list[Project]:
        project_type = project_type if project_type in VALID_PROJECT_TYPES else None
        return self.repo.list(project_type=project_type)


class GetProject:
    def __init__(self, repo: IProjectRepository):
        self.repo = repo

    def execute(self, project_id: str) -> Project:
        return self.repo.get(project_id)


class CreateProject:
    def __init__(self, repo: IProjectRepository):
        self.repo = repo

    def execute(
        self,
        name: str,
        channel_name: str = '',
        owner_id: int | None = None,
        project_type: str = 'gopro',
        highlight_settings: dict | None = None,
    ) -> Project:
        project_type = project_type if project_type in VALID_PROJECT_TYPES else 'gopro'
        settings = dict(DEFAULT_HIGHLIGHT_SETTINGS)
        if project_type == 'futebol' and highlight_settings:
            settings.update({k: v for k, v in highlight_settings.items() if k in settings})

        project = Project(
            id=str(uuid.uuid4()),
            name=name.strip(),
            channel_name=channel_name.strip(),
            phase='new',
            project_type=project_type,
            highlight_settings=settings if project_type == 'futebol' else {},
            owner_id=owner_id,
        )
        return self.repo.save(project)
