from sqlalchemy import text
from sqlalchemy.engine import Connection

from tests.domain.persisted_object import PersistedEventType, PersistedProject


class EventTypeProbe:
    def __init__(self, connection: Connection):
        self.connection = connection

    def exists_by_project_and_code(
        self,
        project: PersistedProject,
        code: str,
    ) -> bool:
        result = self.connection.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM outbox.event_type
                    WHERE project_id = :project_id
                    AND code = :code
                )
                """
            ),
            {
                "project_id": project.id,
                "code": code,
            },
        )

        return bool(result.scalar_one())