from pydantic import BaseModel


class DestinationConfig(BaseModel):
    name: str
    type: str
    url: str | None = None


class RoutingConfig(BaseModel):
    project: str
    destinations: list[DestinationConfig]