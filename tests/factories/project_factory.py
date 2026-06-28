from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from tests.domain.persisted_object import PersistedProject


@dataclass(frozen=True)
class ProjectRecord:
    """
    Test data contract used to create a persisted project.

    This object represents the minimal test-facing contract for inserting a
    valid project row without exposing ORM models.
    """

    name: str
    description: Optional[str] = None
    is_active: bool = True


class ProjectFactory:
    """
    SQL factory used to insert valid project rows in tests.

    This factory intentionally does not use ORM models or application
    repositories. It creates database state required by tests.
    """

    def __init__(self, connection: Connection):
        self.connection = connection

    def create(
        self,
        record: ProjectRecord,
    ) -> PersistedProject:
        """
        Insert a project row.

        Args:
            record: Project data to persist.

        Returns:
            Persisted project identifier.
        """
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

        project_id = int(result.scalar_one())

        return PersistedProject(
            id=project_id,
            name=record.name,
        )