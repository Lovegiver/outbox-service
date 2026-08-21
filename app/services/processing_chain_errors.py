"""Narrow domain errors for metric compatibility and processing snapshots."""


class ProcessingChainError(ValueError):
    """Base class for expected processing-chain administration failures."""


class ProcessingChainSelectionError(ProcessingChainError):
    """Raised when the requested metric-version selection is incoherent."""


class ProcessingChainIncompleteError(ProcessingChainError):
    """Raised when a chain cannot safely become executable."""


class ProcessingChainConflictError(ProcessingChainError):
    """Raised when a concurrent or state transition conflicts."""


class ProcessingChainNotFoundError(ProcessingChainError):
    """Raised when a requested processing chain does not exist."""
