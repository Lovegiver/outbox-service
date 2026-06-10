from enum import StrEnum


class EventStatus(StrEnum):
    RECEIVED = "RECEIVED"
    ROUTED = "ROUTED"
    COMPLETED = "COMPLETED"
    UNROUTABLE = "UNROUTABLE"
    FAILED = "FAILED"