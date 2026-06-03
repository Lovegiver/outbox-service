from dataclasses import dataclass


@dataclass(frozen=True)
class EventScope:
    project_id: int
    event_type_id: int
    event_id: int

