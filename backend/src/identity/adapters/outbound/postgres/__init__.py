"""Identity's Postgres adapters, and the metadata a migration or a fixture creates."""

from identity.adapters.outbound.postgres._tables import SCHEMA, credentials, metadata
from identity.adapters.outbound.postgres.repositories import PostgresCredentialRepository

__all__ = [
    "SCHEMA",
    "PostgresCredentialRepository",
    "credentials",
    "metadata",
]
