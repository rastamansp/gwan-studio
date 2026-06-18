import uuid
from domain.entities import Project
from domain.ports import IProjectRepository


class ListProjects:
    def __init__(self, repo: IProjectRepository):
        self.repo = repo

    def execute(self) -> list[Project]:
        return self.repo.list()


class GetProject:
    def __init__(self, repo: IProjectRepository):
        self.repo = repo

    def execute(self, project_id: str) -> Project:
        return self.repo.get(project_id)


class CreateProject:
    def __init__(self, repo: IProjectRepository):
        self.repo = repo

    def execute(self, name: str, channel_name: str = '') -> Project:
        project = Project(
            id=str(uuid.uuid4()),
            name=name.strip(),
            channel_name=channel_name.strip(),
            phase='new',
        )
        return self.repo.save(project)
