"""The domain layer: what a credential is, and what makes one valid."""

from identity.domain.credential import Credential
from identity.domain.errors import (
    CredentialInactiveError,
    IdentityError,
    InvalidLoginIdError,
    InvalidPasswordError,
    InvalidPasswordHashError,
    InvalidScopeError,
    MissingIdentifierError,
)
from identity.domain.values import MINIMUM_PASSWORD_LENGTH, PasswordHash, Role, Scope, ScopeKind

__all__ = [
    "MINIMUM_PASSWORD_LENGTH",
    "Credential",
    "CredentialInactiveError",
    "IdentityError",
    "InvalidLoginIdError",
    "InvalidPasswordError",
    "InvalidPasswordHashError",
    "InvalidScopeError",
    "MissingIdentifierError",
    "PasswordHash",
    "Role",
    "Scope",
    "ScopeKind",
]
