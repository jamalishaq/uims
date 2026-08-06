"""Identity's one repository port, against Postgres.

``Credential`` reconstitutes through :meth:`Credential.restore` rather than its constructor —
see that method on why the named door exists even where there are no transitions to replay.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import Row, Table
from sqlalchemy.ext.asyncio import AsyncEngine

from identity.adapters.outbound.postgres import _tables as t
from identity.adapters.outbound.postgres._repository import PostgresRepository
from identity.domain.credential import Credential
from identity.domain.values import PasswordHash, Role, Scope, ScopeKind
from identity.ports.credential_repository import CredentialRepositoryPort


class PostgresCredentialRepository(PostgresRepository[Credential], CredentialRepositoryPort):
    """Holds credentials in Postgres. Both lookups become indexes rather than scans."""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(engine, label="credential", table=t.credentials, key=("credential_id",))

    def identity_of(self, aggregate: Credential) -> tuple[str]:
        return (aggregate.credential_id,)

    def row_of(self, aggregate: Credential) -> dict[str, Any]:
        return {
            "credential_id": aggregate.credential_id,
            "login_id": aggregate.login_id,
            "principal_id": aggregate.principal_id,
            "role": aggregate.role.value,
            "scope_kind": aggregate.scope.kind.value,
            "scope_id": aggregate.scope.unit_id,
            "password_hash": aggregate.password_hash.encoded,
            "is_active": aggregate.is_active,
        }

    def restore(self, row: Row[Any], children: Mapping[Table, Sequence[Row[Any]]]) -> Credential:
        """Through ``restore``, which validates the combination the row describes.

        A row whose ``role`` and ``scope_kind`` disagree — a faculty credential scoped to a
        student — is refused here rather than becoming a credential no scope check knows how to
        evaluate. Writing the fields onto an instance directly would skip exactly that.
        """
        return Credential.restore(
            credential_id=row.credential_id,
            login_id=row.login_id,
            principal_id=row.principal_id,
            role=Role(row.role),
            scope=Scope(ScopeKind(row.scope_kind), row.scope_id),
            password_hash=PasswordHash(row.password_hash),
            is_active=row.is_active,
        )

    async def add(self, credential: Credential) -> None:
        await self._add(credential)

    async def save(self, credential: Credential) -> None:
        await self._save(credential)

    async def get(self, credential_id: str) -> Credential | None:
        return await self._get(credential_id)

    async def find_by_login_id(self, login_id: str) -> Credential | None:
        """An index, where the in-memory adapter scanned."""
        if not isinstance(login_id, str) or not login_id.strip():
            return None
        return await self._find_one(t.credentials.c.login_id == login_id.strip())

    async def find_by_principal(self, principal_id: str) -> Credential | None:
        """``None`` for a blank id, before any query is made."""
        if not principal_id:
            return None
        return await self._find_one(t.credentials.c.principal_id == principal_id)

    async def all(self) -> list[Credential]:
        return list(await self._list())
