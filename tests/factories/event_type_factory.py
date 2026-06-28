from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from tests.domain.persisted_object import PersistedEventType, PersistedProject


@dataclass(frozen=True)
class EventTypeRecord:
    project: PersistedProject
    code: str
    name: str
    description: Optional[str] = None
    is_active: bool = True


class EventTypeFactory:
    def __init__(self, connection: Connection):
        self.connection = connection

    def create(self, record: EventTypeRecord) -> PersistedEventType:
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

        event_type_id = int(result.scalar_one())

        return PersistedEventType(
            id=event_type_id,
            project=record.project,
            code=record.code,
            name=record.name,
        )