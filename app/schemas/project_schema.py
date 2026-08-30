import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

PROJECT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def _contains_control_characters(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _validate_project_name(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("Project name must not be empty")
    if len(normalized) > 20:
        raise ValueError("Project name must contain at most 20 characters")
    if PROJECT_NAME_PATTERN.fullmatch(normalized) is None:
        raise ValueError(
            "Project name may contain only letters, numbers, hyphens and underscores"
        )
    return normalized


def _validate_project_description(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > 128:
        raise ValueError("Project description must contain at most 128 characters")
    if _contains_control_characters(normalized):
        raise ValueError("Project description must not contain control characters")
    return normalized


class ProjectCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _validate_project_name(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: Optional[str]) -> Optional[str]:
        return _validate_project_description(value)


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _validate_project_name(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: Optional[str]) -> Optional[str]:
        return _validate_project_description(value)

    @model_validator(mode="after")
    def validate_explicit_name(self) -> "ProjectUpdateRequest":
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("Project name must not be null")
        return self

    def provided_values(self) -> dict[str, Optional[str]]:
        return self.model_dump(exclude_unset=True)


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}
