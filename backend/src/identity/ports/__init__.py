"""Outbound ports: what this context needs from the outside to do its job."""

from identity.ports.credential_repository import CredentialRepositoryPort
from identity.ports.errors import (
    AggregateNotFoundError,
    DuplicateAggregateError,
    PersistenceUnavailableError,
    RepositoryError,
    TokenIssuanceError,
)
from identity.ports.token_issuer import IssuedTokens, TokenIssuerPort

__all__ = [
    "AggregateNotFoundError",
    "CredentialRepositoryPort",
    "DuplicateAggregateError",
    "IssuedTokens",
    "PersistenceUnavailableError",
    "RepositoryError",
    "TokenIssuanceError",
    "TokenIssuerPort",
]
