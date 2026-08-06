"""Outbound port for storing and retrieving credentials."""

from abc import ABC, abstractmethod

from identity.domain.credential import Credential


class CredentialRepositoryPort(ABC):
    """Persistence for the ``Credential`` aggregate."""

    @abstractmethod
    async def add(self, credential: Credential) -> None:
        """Store a new credential.

        Raises:
            DuplicateAggregateError: the credential id or the login id is already held.
        """

    @abstractmethod
    async def save(self, credential: Credential) -> None:
        """Persist changes to a credential that is already stored.

        Raises:
            AggregateNotFoundError: the credential id was never added.
        """

    @abstractmethod
    async def get(self, credential_id: str) -> Credential | None:
        """Return the credential, or ``None`` if no such id is held."""

    @abstractmethod
    async def find_by_login_id(self, login_id: str) -> Credential | None:
        """Return the credential with this login id, or ``None``.

        The lookup the whole context exists for, and the only one a login flow makes. ``None``
        is a normal answer — somebody mistyped a username — and is deliberately indistinguishable
        from a wrong password by the time it reaches a client.
        """

    @abstractmethod
    async def find_by_principal(self, principal_id: str) -> Credential | None:
        """Return the credential issued to this principal, or ``None``.

        What makes credential creation idempotent. The seeder and any future provisioning flow
        run more than once against the same university, and without this each run would issue a
        second credential to a lecturer who already has one — leaving two live passwords for one
        person and no way to tell which the person is using.
        """

    @abstractmethod
    async def all(self) -> list[Credential]:
        """Every credential held. For administration, never for a login flow."""
