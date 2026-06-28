from sqlalchemy import text
from sqlalchemy.engine import Connection


class ProjectProbe:
    """
    Read-only SQL probe used to observe persisted projects in tests.

    This probe intentionally does not use ORM models or application
    repositories. It exists to validate observable database state from tests.
    """

    def __init__(self, connection: Connection):
        """
        Initialize the probe.

        Args:
            connection: SQLAlchemy connection bound to the current test
                transaction.
        """
        self.connection = connection

    def exists_by_name(self, name: str) -> bool:
        """
        Check whether a project exists with the given name.

        Args:
            name: Project name to look for.

        Returns:
            True if a matching project exists, False otherwise.
        """
        result = self.connection.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM outbox.project
                    WHERE name = :name
                )
                """
            ),
            {"name": name},
        )

        return bool(result.scalar_one())