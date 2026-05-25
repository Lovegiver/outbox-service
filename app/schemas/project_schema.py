from pydantic import BaseModel


class ProjectCreateRequest(BaseModel):
    name: str
    description: str | None = None


class ProjectUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None
    is_active: bool

    model_config = {
        "from_attributes": True
    }