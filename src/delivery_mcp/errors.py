class DeliveryMcpError(Exception):
    """Base error for delivery-mcp."""


class StorageError(DeliveryMcpError):
    """Persistent state failure."""


class ValidationError(DeliveryMcpError):
    """Input validation failure."""


class TransitionError(DeliveryMcpError):
    """Invalid status transition or gate violation."""
