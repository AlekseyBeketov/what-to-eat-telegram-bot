class DomainError(Exception):
    """Expected business-rule failure safe to show to a user."""


class NotFoundError(DomainError):
    pass


class AccessDeniedError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class InvalidInviteError(DomainError):
    pass
