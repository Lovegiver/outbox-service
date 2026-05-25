from pydantic import BaseModel, Field


class SchemaDefinitionCreate(BaseModel):
    json_version_client: str | None = Field(default=None, max_length=30)
    json_version_internal: str = Field(default="1.0", max_length=30)
    json_schema: dict


class SchemaDefinitionRead(BaseModel):
    id: int
    event_type_id: int
    json_version_client: str | None
    json_version_internal: str
    json_schema: dict
    is_active: bool

    model_config = {
        "from_attributes": True
    }