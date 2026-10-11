"""Domain exceptions.

Messages are user-facing, so they are written in Spanish; the UI shows them as they are.
"""


class DomainError(Exception):
    """Base class for every error the user can act on."""


class ValidationError(DomainError):
    """A value does not meet a business rule."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


class NotFoundError(DomainError):
    """The requested record does not exist."""


class DuplicateError(DomainError):
    """A record with the same unique key already exists."""


class InvalidStateError(DomainError):
    """The operation is not allowed in the record's current state (e.g. deactivating twice)."""
