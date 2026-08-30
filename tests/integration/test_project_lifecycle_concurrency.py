from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Optional
from uuid import uuid4

from sqlalchemy import text

from app.database import SessionLocal, engine
from app.models.project import Project
from app.repositories.project_member_repository import ProjectMemberRepository
from app.repositories.project_repository import ProjectRepository
from app.services.project_errors import ProjectConflictError
from app.services.project_service import ProjectService
from tests.domain.record import ProjectRecord
from tests.infrastructure.object_factory import ObjectFactory


class SynchronizedNameLookupRepository(ProjectRepository):
    def __init__(self, db, barrier: Barrier, target_name: str) -> None:
        super().__init__(db)
        self.barrier = barrier
        self.target_name = target_name

    def find_by_name(
        self,
        name: str,
        exclude_project_id: Optional[int] = None,
    ) -> Optional[Project]:
        project = super().find_by_name(name, exclude_project_id)
        if name == self.target_name:
            self.barrier.wait(timeout=10)
        return project


def _rename(project_id: int, target_name: str, barrier: Barrier) -> str:
    with SessionLocal() as session:
        service = ProjectService(
            db=session,
            project_repository=SynchronizedNameLookupRepository(
                session,
                barrier,
                target_name,
            ),
            project_member_repository=ProjectMemberRepository(session),
        )
        try:
            service.update_project(project_id, {"name": target_name})
            return "updated"
        except ProjectConflictError:
            return "conflict"


def test_concurrent_renames_preserve_global_uniqueness() -> None:
    suffix = uuid4().hex[:10]
    first_name = f"first-{suffix}"
    second_name = f"second-{suffix}"
    target_name = f"target-{suffix}"

    with engine.begin() as connection:
        factory = ObjectFactory(connection)
        first = factory.project(ProjectRecord(name=first_name))
        second = factory.project(ProjectRecord(name=second_name))

    barrier = Barrier(2)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    lambda project_id: _rename(project_id, target_name, barrier),
                    (first.id, second.id),
                )
            )

        assert sorted(results) == ["conflict", "updated"]
        with engine.begin() as connection:
            target_count = connection.execute(
                text("SELECT COUNT(*) FROM outbox.project WHERE name = :name"),
                {"name": target_name},
            ).scalar_one()
            source_count = connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM outbox.project
                    WHERE name IN (:first_name, :second_name)
                    """
                ),
                {"first_name": first_name, "second_name": second_name},
            ).scalar_one()
        assert target_count == 1
        assert source_count == 1
    finally:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    DELETE FROM outbox.project
                    WHERE name IN (:first_name, :second_name, :target_name)
                    """
                ),
                {
                    "first_name": first_name,
                    "second_name": second_name,
                    "target_name": target_name,
                },
            )
