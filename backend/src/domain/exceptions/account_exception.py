from .base import UnauthorizedActionException, NotFoundException, ConflictException

class AccountNotFoundException(NotFoundException):
    code = "IDENTITY_ACCOUNT_NOT_FOUND"

    def __init__(self, email: str | None = None, account_id: str | None = None):
        self.email = email
        super().__init__(f"Account with this credential '{email | account_id}' was not found.")


AccountAccountNotFoundException = AccountNotFoundException


class InvalidJWTTokenException(UnauthorizedActionException):
    code = "IDENTITY_INVALID_JWT_TOKEN"

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"JWT token validation failed: {reason}")

class IncorrectPasswordException(UnauthorizedActionException):
    code = "IDENTITY_INCORRECT_PASSWORD"

    def __init__(self, passowrd: str):
        self.passowrd = passowrd
        super().__init__(f"Password matching failed: {passowrd}")

class InsufficientPermissionsException(UnauthorizedActionException):
    code = "IDENTITY_INSUFFICIENT_PERMISSIONS"

    def __init__(self, account_id: str, action: str, resource_type: str, account_active_role: str):
        self.account_id = account_id
        self.action = action
        self.resource_type = resource_type
        self.account_active_role = account_active_role
        super().__init__(
            f" {account_id} with role '{account_active_role}' is not permitted to "
            f"perform '{action}' on resource type '{resource_type}'."
        )

class RoleAssumingException(UnauthorizedActionException):
    code = "IDENTITY_ROLE_ASSUMING"

    def __init__(self, account_id: str, role: str):
        self.account_id = account_id
        self.role = role
        super().__init__(f" '{account_id}' cannot assume role '{role}'")

class DuplicateAccountProvisioningException(ConflictException):
    code = "IDENTITY_DUPLICATE_ACCOUNT_PROVISIONING"

    def __init__(self, entity_id: str, existing_account_id: str):
        self.entity_id = entity_id
        self.existing_account_id = existing_account_id
        super().__init__(
            f"Entity {entity_id} already has a linked account "
            f"({existing_account_id})."
        )