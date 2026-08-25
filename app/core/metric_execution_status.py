from enum import StrEnum


class MetricProcessingStatus(StrEnum):
    """Durable lifecycle of one Event metric snapshot."""

    MATERIALIZED = "MATERIALIZED"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED_CONFIGURATION = "FAILED_CONFIGURATION"


class MetricPlanExecutionStatus(StrEnum):
    """Durable lifecycle of one Event/ProcessingPlan execution."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    RETRYABLE = "RETRYABLE"
    SUCCEEDED = "SUCCEEDED"
    FAILED_PERMANENT = "FAILED_PERMANENT"
