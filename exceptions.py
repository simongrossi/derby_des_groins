class BusinessRuleError(Exception):
    """Base class for domain-level business errors."""


class NotFoundError(BusinessRuleError):
    """Raised when a requested entity cannot be found."""


class UserNotFoundError(NotFoundError):
    """Raised when a user cannot be found."""


class PigNotFoundError(NotFoundError):
    """Raised when a pig cannot be found."""


class InsufficientFundsError(BusinessRuleError):
    """Raised when a user does not have enough balance."""


class PigTiredError(BusinessRuleError):
    """Raised when a pig cannot perform an action because of its state."""


class ValidationError(BusinessRuleError):
    """Raised when user input or action preconditions are invalid."""
