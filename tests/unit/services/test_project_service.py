from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.project import Project
from app.services.project_errors import (
    ProjectConflictError,
    ProjectNotFoundError,
    ProjectValidationError,
)
from app.services.project_service import ProjectService


def _service() -> tuple[ProjectService, MagicMock, MagicMock, MagicMock]:
    db = MagicMock()
    projects = MagicMock()
    members = MagicMock()
    return ProjectService(db, projects, members), db, projects, members


def test_get_project_returns_targeted_project() -> None:
    service, _, projects, _ = _service()
    project = Project(id=1, name="hermes", is_active=False)
    projects.find_by_id.return_value = project

    assert service.get_project(1) is project
    projects.find_by_id.assert_called_once_with(1)


def test_get_project_rejects_unknown_id() -> None:
    service, _, projects, _ = _service()
    projects.find_by_id.return_value = None

    with pytest.raises(ProjectNotFoundError):
        service.get_project(404)


def test_update_applies_only_provided_fields_and_commits_once() -> None:
    service, db, projects, _ = _service()
    project = Project(id=1, name="hermes", description="kept", is_active=True)
    projects.find_by_id_for_update.return_value = project
    projects.find_by_name.return_value = None
    projects.update.return_value = project

    result = service.update_project(1, {"name": "apollo"})

    assert result.name == "apollo"
    assert result.description == "kept"
    db.commit.assert_called_once_with()
    db.rollback.assert_not_called()
    projects.update.assert_called_once_with(project)


def test_update_can_explicitly_clear_description() -> None:
    service, _, projects, _ = _service()
    project = Project(id=1, name="hermes", description="remove", is_active=True)
    projects.find_by_id_for_update.return_value = project
    projects.update.return_value = project

    service.update_project(1, {"description": None})

    assert project.description is None


def test_update_rejects_empty_payload_without_write() -> None:
    service, db, projects, _ = _service()

    with pytest.raises(ProjectValidationError) as exc_info:
        service.update_project(1, {})

    assert exc_info.value.code == "PROJECT_UPDATE_EMPTY"
    projects.find_by_id_for_update.assert_not_called()
    db.commit.assert_not_called()


def test_update_rejects_existing_name_and_rolls_back() -> None:
    service, db, projects, _ = _service()
    project = Project(id=1, name="hermes", is_active=True)
    projects.find_by_id_for_update.return_value = project
    projects.find_by_name.return_value = Project(id=2, name="apollo", is_active=True)

    with pytest.raises(ProjectConflictError):
        service.update_project(1, {"name": "apollo"})

    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()
    assert project.name == "hermes"


def test_integrity_conflict_is_translated_after_rollback() -> None:
    service, db, projects, _ = _service()
    project = Project(id=1, name="hermes", is_active=True)
    projects.find_by_id_for_update.return_value = project
    projects.find_by_name.return_value = None
    projects.update.side_effect = IntegrityError("statement", {}, Exception("unique"))

    with pytest.raises(ProjectConflictError):
        service.update_project(1, {"name": "apollo"})

    db.rollback.assert_called_once_with()
    db.commit.assert_not_called()


@pytest.mark.parametrize("initial", [True, False])
def test_enable_is_idempotent(initial: bool) -> None:
    service, db, projects, _ = _service()
    project = Project(id=1, name="hermes", is_active=initial)
    projects.find_by_id_for_update.return_value = project
    projects.enable.side_effect = lambda target: (
        setattr(target, "is_active", True) or target
    )

    result = service.enable_project(1)

    assert result.is_active is True
    db.commit.assert_called_once_with()
    if initial:
        projects.enable.assert_not_called()
    else:
        projects.enable.assert_called_once_with(project)


def test_enable_rolls_back_unexpected_error() -> None:
    service, db, projects, _ = _service()
    projects.find_by_id_for_update.side_effect = RuntimeError("database unavailable")

    with pytest.raises(RuntimeError):
        service.enable_project(1)

    db.rollback.assert_called_once_with()
