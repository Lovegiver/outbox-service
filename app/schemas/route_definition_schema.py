from typing import Any

from pydantic import BaseModel

from app.core.auth_type import AuthType


class RouteDefinitionCreateRequest(BaseModel):
    routing_key: str
    destination_name: str
    destination_url: str
    auth_type: AuthType = AuthType.NONE
    auth_config: dict[str, Any] | None = None
    secret_ref: str | None = None

class RouteDefinitionUpdateRequest(BaseModel):
    routing_key: str | None = None
    destination_name: str | None = None
    destination_url: str | None = None
    auth_type: AuthType | None = None
    auth_config: dict[str, Any] | None = None
    secret_ref: str | None = None

class RouteDefinitionResponse(BaseModel):
    id: int
    event_type_id: int
    routing_key: str
    destination_name: str
    destination_url: str
    is_active: bool
    auth_type: str
    auth_config: dict[str, Any] | None
    secret_ref: str | None

    model_config = {
        "from_attributes": True
    }
