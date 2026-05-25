from pydantic import BaseModel, Field


class EventTypeCreate(BaseModel):
    project_id: int
    code: str = Field(min_length=1, max_length=150)
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=255)


class EventTypeRead(BaseModel):
    id: int
    project_id: int
    code: str
    name: str
    description: str | None
    is_active: bool

    model_config = {
        "from_attributes": True
    }