from pydantic import BaseModel


class RouteDefinitionCreateRequest(BaseModel):
    routing_key: str
    destination_name: str
    destination_url: str


class RouteDefinitionResponse(BaseModel):
    id: int
    event_type_id: int
    routing_key: str
    destination_name: str
    destination_url: str
    is_active: bool

    model_config = {
        "from_attributes": True
    }