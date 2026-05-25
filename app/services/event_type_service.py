from app.models.event_type import EventType
from app.repositories.event_type_repository import EventTypeRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.event_type_schema import EventTypeCreate


class EventTypeService:
    def __init__(
        self,
        event_type_repository: EventTypeRepository,
        project_repository: ProjectRepository,
    ):
        self.event_type_repository = event_type_repository
        self.project_repository = project_repository

    def create_event_type(self, payload: EventTypeCreate) -> EventType:
        project = self.project_repository.find_by_id(payload.project_id)

        if project is None:
            raise ValueError(f"Project {payload.project_id} not found")

        if not project.is_active:
            raise ValueError(f"Project {payload.project_id} is not active")

        existing = self.event_type_repository.find_by_project_id_and_code(
            project_id=payload.project_id,
            code=payload.code,
        )

        if existing is not None:
            raise ValueError(
                f"EventType '{payload.code}' already exists for project {payload.project_id}"
            )

        event_type = EventType(
            project_id=payload.project_id,
            code=payload.code,
            name=payload.name,
            description=payload.description,
            is_active=True,
        )

        return self.event_type_repository.create(event_type)

    def get_event_type(self, event_type_id: int) -> EventType:
        event_type = self.event_type_repository.find_by_id(event_type_id)

        if event_type is None:
            raise ValueError(f"EventType {event_type_id} not found")

        return event_type

    def list_by_project(self, project_id: int) -> list[EventType]:
        project = self.project_repository.find_by_id(project_id)

        if project is None:
            raise ValueError(f"Project {project_id} not found")

        return self.event_type_repository.find_by_project_id(project_id)