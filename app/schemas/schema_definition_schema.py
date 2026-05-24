from pydantic import BaseModel


class SchemaDefinitionCreateRequest(BaseModel):
    event_type_id: int
    name: str
    version: str
    json_schema: dict


class SchemaDefinitionResponse(BaseModel):
    id: int
    event_type_id: int
    name: str
    version: str
    json_schema: dict
    enabled: bool

    model_config = {
        "from_attributes": True
    }