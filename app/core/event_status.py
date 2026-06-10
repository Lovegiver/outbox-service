from enum import StrEnum


class EventStatus(StrEnum):
    RECEIVED = "RECEIVED"
    ROUTED = "ROUTED"
    UNROUTABLE = "UNROUTABLE"
    FAILED = "FAILED"