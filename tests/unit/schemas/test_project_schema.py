from typing import Optional

import pytest
from pydantic import ValidationError

from app.schemas.project_schema import ProjectCreateRequest, ProjectUpdateRequest


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" Hermes ", "hermes"),
        ("project_1", "project_1"),
        ("project-1", "project-1"),
    ],
)
def test_project_name_is_normalized(raw: str, expected: str) -> None:
    assert ProjectCreateRequest(name=raw).name == expected


@pytest.mark.parametrize(
    "name",
    ["", "   ", "project name", "project.name", "<script>", "x" * 21],
)
def test_invalid_project_name_is_rejected(name: str) -> None:
    with pytest.raises(ValidationError):
        ProjectUpdateRequest(name=name)


def test_patch_distinguishes_absent_and_explicit_null_description() -> None:
    absent = ProjectUpdateRequest(name="renamed")
    cleared = ProjectUpdateRequest(description=None)

    assert absent.provided_values() == {"name": "renamed"}
    assert cleared.provided_values() == {"description": None}


def test_patch_rejects_explicit_null_name() -> None:
    with pytest.raises(ValidationError):
        ProjectUpdateRequest(name=None)


def test_empty_description_is_normalized_to_none() -> None:
    request = ProjectUpdateRequest(description="   ")
    assert request.description is None
    assert request.provided_values() == {"description": None}


@pytest.mark.parametrize(
    "description", ["safe <script>alert(1)</script>", "'; DROP TABLE event; --"]
)
def test_free_text_description_remains_inert(description: str) -> None:
    request = ProjectUpdateRequest(description=description)
    assert request.description == description


@pytest.mark.parametrize("description", ["bad\nvalue", "bad\x00value", "x" * 129])
def test_invalid_description_is_rejected(description: str) -> None:
    with pytest.raises(ValidationError):
        ProjectUpdateRequest(description=description)


def test_update_request_does_not_mutate_input_mapping() -> None:
    payload: dict[str, Optional[str]] = {
        "name": " New_Name ",
        "description": " Description ",
    }
    original = payload.copy()

    ProjectUpdateRequest.model_validate(payload)

    assert payload == original
