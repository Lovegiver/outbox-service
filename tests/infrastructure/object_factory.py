from sqlalchemy import text
from sqlalchemy.engine import Connection

from tests.domain.persisted_object import PersistedEventType, PersistedProject
from tests.domain.record import EventTypeRecord, ProjectRecord


class ObjectFactory:
    def __init__(self, connection: Connection):
        self.connection = connection

    def create_project(self, record: ProjectRecord) -> PersistedProject:
        result = self.connection.execute(
            text(
                """
                INSERT INTO outbox.project (
                    name,
                    description,
                    is_active
                )
                VALUES (
                    :name,
                    :description,
                    :is_active
                )
                RETURNING id
                """
            ),
            {
                "name": record.name,
                "description": record.description,
                "is_active": record.is_active,
            },
        )

        return PersistedProject(
            id=int(result.scalar_one()),
            name=record.name,
        )

    def create_event_type(
        self,
        record: EventTypeRecord,
    ) -> PersistedEventType:
        result = self.connection.execute(
            text(
                """
                INSERT INTO outbox.event_type (
                    project_id,
                    code,
                    name,
                    description,
                    is_active
                )
                VALUES (
                    :project_id,
                    :code,
                    :name,
                    :description,
                    :is_active
                )
                RETURNING id
                """
            ),
            {
                "project_id": record.project.id,
                "code": record.code,
                "name": record.name,
                "description": record.description,
                "is_active": record.is_active,
            },
        )

        return PersistedEventType(
            id=int(result.scalar_one()),
            project=record.project,
            code=record.code,
            name=record.name,
        )