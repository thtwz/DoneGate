class DoneGateMcpError(Exception):
    """Base error for donegate-mcp."""


class StorageError(DoneGateMcpError):
    """Persistent state failure."""


class ValidationError(DoneGateMcpError):
    """Input validation failure."""


class TransitionError(DoneGateMcpError):
    """Invalid status transition or gate violation."""
