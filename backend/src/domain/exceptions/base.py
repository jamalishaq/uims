from abc import ABC



# ---- Base exception ----
class DomainException(ABC, Exception):
    code: str

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


# ---- Category-level base exceptions ----
class NotFoundException(DomainException, ABC):
    pass


class ConflictException(DomainException, ABC):
    pass


class BusinessRuleViolationException(DomainException, ABC):
    pass


class ValidationException(DomainException, ABC):
    pass


class UnauthorizedActionException(DomainException, ABC):
    pass


class ExternalServiceException(DomainException, ABC):
    pass