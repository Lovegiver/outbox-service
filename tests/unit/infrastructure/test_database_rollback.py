from tests.domain.persisted_object import PersistedProject
from tests.domain.record import ProjectRecord


def test_database_rollback_creates_temporary_project(ctx) -> None:
    project = ctx.factory.project(
        ProjectRecord(name="Temporary rollback project")
    )

    ctx.assertions.exists(
        ctx.probe.project,
        project,
    )


def test_database_rollback_removed_previous_test_data(ctx) -> None:
    previous_project = PersistedProject(
        id=999999,
        name="Temporary rollback project",
    )

    assert not ctx.probe.project.exists_by_name(previous_project.name)
