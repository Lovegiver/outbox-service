"""Narrow public errors for Metrics Builder validation."""


class MetricBuilderError(ValueError):
    """Base class for deterministic Builder errors safe for API clients."""

    code = "METRIC_BUILDER_ERROR"

    def __init__(self, message: str) -> None:
        """Store a stable code and a non-sensitive human-readable message."""
        super().__init__(message)
        self.message = message

    def public_message(self) -> str:
        """Return the stable API representation of this error."""
        return f"{self.code}: {self.message}"


class MetricBuilderNotFoundError(MetricBuilderError):
    """Raised when the requested exact schema does not exist."""

    code = "BUILDER_SCHEMA_NOT_FOUND"


class MetricBuilderScopeError(MetricBuilderError):
    """Raised when a schema belongs to another EventType."""

    code = "BUILDER_SCHEMA_OUT_OF_SCOPE"


class MetricBuilderContractError(MetricBuilderError):
    """Raised when a requested intent violates the Builder contract."""

    code = "BUILDER_CONTRACT_INVALID"


class MetricBuilderUnsupportedError(MetricBuilderError):
    """Raised when a schema construction cannot be analyzed safely."""

    code = "BUILDER_SCHEMA_UNSUPPORTED"


class MetricBuilderUnsafeError(MetricBuilderError):
    """Raised when an understood configuration is unsafe for Counters."""

    code = "BUILDER_COUNTER_UNSAFE"


class MetricBuilderCardinalityBudgetError(MetricBuilderUnsafeError):
    """Raised when an EventType snapshot exceeds its static series budget."""

    code = "BUILDER_CARDINALITY_BUDGET_EXCEEDED"


class MetricBuilderCardinalityUnboundedError(MetricBuilderUnsafeError):
    """Raised when a requested static series bound cannot be demonstrated."""

    code = "BUILDER_CARDINALITY_UNBOUNDED"


class MetricBuilderNameCollisionError(MetricBuilderError):
    """Raised when distinct metric codes normalize to the same series name."""

    code = "BUILDER_PROMETHEUS_NAME_COLLISION"


class MetricBuilderAlreadyExistsError(MetricBuilderError):
    """Raised when one natural metric key has different functional content."""

    code = "BUILDER_METRIC_ALREADY_EXISTS"


class MetricBuilderCreationConflictError(MetricBuilderError):
    """Raised when persistence detects an incompatible concurrent creation."""

    code = "BUILDER_CREATION_CONFLICT"
