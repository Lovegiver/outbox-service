from typing import Protocol


class HasProjectId(Protocol):
    project_id: int