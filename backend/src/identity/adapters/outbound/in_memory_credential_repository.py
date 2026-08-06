"""Dict-backed ``CredentialRepositoryPort``."""

from identity.adapters.outbound._store import InMemoryStore
from identity.domain.credential import Credential
from identity.ports.credential_repository import CredentialRepositoryPort
from identity.ports.errors import DuplicateAggregateError


class InMemoryCredentialRepository(CredentialRepositoryPort):
    """Holds credentials in memory for the duration of the process."""

    def __init__(self) -> None:
        self._store = InMemoryStore[Credential](
            "credential", lambda credential: credential.credential_id
        )

    async def add(self, credential: Credential) -> None:
        """Refuses a duplicate login id as well as a duplicate credential id.

        The store only knows about the primary key, so the second uniqueness rule is enforced
        here. It has to be enforced *somewhere* in this adapter: the Postgres table carries a
        unique index on ``login_id``, and an in-memory adapter that let a duplicate through
        would make the suite pass on one backend and fail on the other — which is precisely
        what running the same tests against both is meant to catch.
        """
        if await self.find_by_login_id(credential.login_id) is not None:
            raise DuplicateAggregateError(f"login id {credential.login_id} is already stored")
        self._store.add(credential)

    async def save(self, credential: Credential) -> None:
        self._store.save(credential)

    async def get(self, credential_id: str) -> Credential | None:
        return self._store.get(credential_id)

    async def find_by_login_id(self, login_id: str) -> Credential | None:
        """A scan, which a unique index does in Postgres.

        Compared against the *stripped* login id, because that is what ``Credential`` stored.
        A caller passing untrimmed input would otherwise miss a credential that is there.
        """
        wanted = login_id.strip() if isinstance(login_id, str) else login_id
        return next(
            (credential for credential in self._store.all() if credential.login_id == wanted),
            None,
        )

    async def find_by_principal(self, principal_id: str) -> Credential | None:
        """A scan. ``None`` for a blank id, before anything is compared."""
        if not principal_id:
            return None
        return next(
            (
                credential
                for credential in self._store.all()
                if credential.principal_id == principal_id
            ),
            None,
        )

    async def all(self) -> list[Credential]:
        return list(self._store.all())
