from uuid import UUID
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError, DBAPIError

from src.domain.models import Account
from src.domain.exceptions.account_exception import DuplicateAccountProvisioningException
from src.infrastructure.database.orms import AccountORM
from src.infrastructure.database.connection import DatabaseFactory
from src.infrastructure.exceptions import QueryTimeoutException
from src.infrastructure.database import with_circuit_breaker, retry_on_transient_db_error
from src.service.ports.repositories import AccountReporsitoyPort


class AccountRepositoryAdapter(AccountReporsitoyPort):
    def __init__(self, db_factory: DatabaseFactory):
        self.db_factory = db_factory

    @with_circuit_breaker
    @retry_on_transient_db_error(operation_name="account_create")
    async def create(self, account: Account) -> Account:
        async with self.db_factory.session() as session:
            try:
                new_account = self._to_orm(account)
                session.add(new_account)
                await session.commit()
                await session.refresh(new_account)

                return self._to_domain(new_account)
            except IntegrityError as e:
                await session.rollback()
                # Catch unique constraint violations on owner_id or email
                if "entity_id" in str(e.orig) or "owner_id" in str(e.orig):
                    raise DuplicateAccountProvisioningException(
                        entity_id=str(account.owner_id),
                        existing_account_id=str(account.account_id),
                    ) from e
                raise
            except (OperationalError, DBAPIError) as e:
                await session.rollback()
                if "timeout" in str(e.orig).lower():
                    raise QueryTimeoutException(
                        operation="account_create",
                        timeout_seconds=5.0,
                    ) from e

                raise

    @with_circuit_breaker
    @retry_on_transient_db_error(operation_name="account_find_by_id")
    async def find_by_id(self, account_id: UUID) -> Account | None:
        async with self.db_factory.session() as session:
            try:
                query = select(AccountORM).where(AccountORM.account_id == account_id)
                result = await session.execute(query)
                account_orm = result.scalar_one_or_none()

                return self._to_domain(account_orm)
            except (OperationalError, DBAPIError) as e:
                await session.rollback()
                if "timeout" in str(e.orig).lower():
                    raise QueryTimeoutException(
                        operation="account_find_by_id",
                        timeout_seconds=5.0,
                    ) from e

                raise

    @with_circuit_breaker
    @retry_on_transient_db_error(operation_name="account_find_by_email")
    async def find_by_email(self, email: str) -> Account | None:
        async with self.db_factory.session() as session:
            try:
                query = select(AccountORM).where(AccountORM.email == email)
                result = await session.execute(query)
                account_orm = result.scalar_one_or_none()

                return self._to_domain(account_orm)
            except (OperationalError, DBAPIError) as e:
                await session.rollback()
                if "timeout" in str(e.orig).lower():
                    raise QueryTimeoutException(
                        operation="account_find_by_email",
                        timeout_seconds=5.0,
                    ) from e

                raise

    @with_circuit_breaker
    @retry_on_transient_db_error(operation_name="account_find_by_owner_id")
    async def find_by_owner_id(
        self, entity_id: UUID, entity_type: str
    ) -> Account | None:
        async with self.db_factory.session() as session:
            try:
                query = (
                    select(AccountORM)
                    .where(AccountORM.entity_id == entity_id)
                    .where(AccountORM.entity_type == entity_type)
                )
                result = await session.execute(query)
                account_orm = result.scalar_one_or_none()

                return self._to_domain(account_orm)
            except (OperationalError, DBAPIError) as e:
                await session.rollback()
                if "timeout" in str(e.orig).lower():
                    raise QueryTimeoutException(
                        operation="account_find_by_owner_id",
                        timeout_seconds=5.0,
                    ) from e

                raise

    @with_circuit_breaker
    @retry_on_transient_db_error(operation_name="account_update_active_role")
    async def update_active_role(self, account: Account) -> Account:
        async with self.db_factory.session() as session:
            try:
                updated_account_orm = await self._update(session, account)

                return self._to_domain(updated_account_orm)
            except (OperationalError, DBAPIError) as e:
                await session.rollback()
                if "timeout" in str(e.orig).lower():
                    raise QueryTimeoutException(
                        operation="account_update_active_role",
                        timeout_seconds=5.0,
                    ) from e

                raise

    @with_circuit_breaker
    @retry_on_transient_db_error(operation_name="account_update_roles")
    async def update_roles(self, account: Account) -> Account:
        async with self.db_factory.session() as session:
            try:
                updated_account_orm = await self._update(session, account)

                return self._to_domain(updated_account_orm)
            except (OperationalError, DBAPIError) as e:
                await session.rollback()
                if "timeout" in str(e.orig).lower():
                    raise QueryTimeoutException(
                        operation="account_update_roles",
                        timeout_seconds=5.0,
                    ) from e

                raise

    @with_circuit_breaker
    @retry_on_transient_db_error(operation_name="account_update_last_login")
    async def update_last_login(self, account: Account) -> Account:
        async with self.db_factory.session() as session:
            try:
                updated_account_orm = await self._update(session, account)

                return self._to_domain(updated_account_orm)
            except (OperationalError, DBAPIError) as e:
                await session.rollback()
                if "timeout" in str(e.orig).lower():
                    raise QueryTimeoutException(
                        operation="account_update_last_login",
                        timeout_seconds=5.0,
                    ) from e

                raise

    async def _update(self, session, account: Account) -> AccountORM:
        account_orm = self._to_orm(account)
        merged_orm = await session.merge(account_orm)

        await session.commit()
        await session.refresh(merged_orm)

        return merged_orm

    def _to_domain(self, account_orm: AccountORM | None) -> Account | None:
        if account_orm is None:
            return None

        return Account(
            account_id=account_orm.account_id,
            email=account_orm.email,
            password=account_orm.password,
            roles=account_orm.roles,
            active_role=account_orm.active_role,
            owner_id=getattr(account_orm, "owner_id", None) or getattr(account_orm, "entity_id", None),
            is_active=account_orm.is_active,
            last_login_at=account_orm.last_login_at,
        )

    def _to_orm(self, account: Account) -> AccountORM:
        return AccountORM(
            account_id=account.account_id,
            email=account.email,
            password=account.password,
            roles=account.roles,
            active_role=account.active_role,
            owner_id=account.owner_id,
            is_active=account.is_active,
            last_login_at=account.last_login_at,
        )