from enum import StrEnum


class EventStatus(StrEnum):
    RECEIVED = "RECEIVED"
    VALIDATED = "VALIDATED"
    ROUTED = "ROUTED"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"