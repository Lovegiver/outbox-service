from __future__ import annotations

from pydantic import BaseModel


class MetricDefinitionCreate(BaseModel):
    """
    Request payload used to create a metric definition for an EventType.
    """

    code: str
    name: str
    description: str | None = None


class MetricDefinitionRead(BaseModel):
    """
    API representation of a metric definition.
    """

    id: int
    event_type_id: int
    code: str
    name: str
    description: str | None
    is_active: bool

    model_config = {
        "from_attributes": True,
    }


class MetricDefinitionVersionCreate(BaseModel):
    """
    Request payload used to create a YAML version for a metric definition.
    """

    yaml_version_number: int
    yaml_version_label: str | None = None
    yaml_content: str


class MetricDefinitionVersionRead(BaseModel):
    """
    API representation of a metric definition YAML version.
    """

    id: int
    metric_definition_id: int
    yaml_version_number: int
    yaml_version_label: str | None
    yaml_content: str
    is_active: bool

    model_config = {
        "from_attributes": True,
    }


class MetricDefinitionVersionSchemaRead(BaseModel):
    """
    API representation of a validated YAML/schema compatibility.
    """

    id: int
    metric_definition_version_id: int
    schema_definition_id: int

    model_config = {
        "from_attributes": True,
    }