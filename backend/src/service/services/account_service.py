import uuid
import jwt
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from pwdlib import PasswordHash

from src.domain.models import Account, Role
from src.domain.exceptions import InvalidJWTTokenException, RoleAssumingException, IncorrectPasswordException, AccountAccountNotFoundException
from src.service.ports.repositories import AccountReporsitoyPort

SECRET_KEY = "your-super-secret-key"
REFRESH_SECRET_KEY = "your-refresh-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7


class TokenStorePort(Protocol):
    async def save_refresh_token(self, account_id: str, jti: str, ttl_seconds: int) -> None: ...
    async def is_refresh_token_valid(self, account_id: str, jti: str) -> bool: ...
    async def revoke_refresh_token(self, account_id: str, jti: str) -> None: ...
    async def revoke_all_account_tokens(self, account_id: str) -> None: ...


class AccountService:
    def __init__(self, account_repo: AccountReporsitoyPort, token_store: TokenStorePort):
        self.account_repo = account_repo
        self.token_store = token_store
        self.pwd_hash = PasswordHash.recommended()

    # --- Public API Methods ---

    async def create_account(self, account_details: dict[str, Any]) -> Account:
        new_account = Account(
            account_id=uuid.uuid4(),
            email=account_details.email,
            password=account_details.password,
            active_role=Role(account_details.active_role),
            roles=[Role(role) for role in account_details.roles],
            owner_id=account_details.owner_id,
            is_active=account_details.is_active,
        )
        saved_account = await self.account_repo.create(new_account)

        return saved_account

    async def login(self, email: str, password: str) -> dict[str, str] | None:
        account = await self.account_repo.find_by_email(email)
        if not account:
            raise AccountAccountNotFoundException(email)
        
        if not self._verify_password(password, account.password):
            raise IncorrectPasswordException(password)

        return await self._generate_token_pair(account)

    async def add_role(self, account_id: str, roles_to_add: list[Role | str]) -> Account | None:
        # 1. Fetch account aggregate from repository
        account = await self.account_repo.find_by_id(account_id)
        if not account:
            raise AccountAccountNotFoundException(str(account_id))

        # 2. Normalize input roles to domain Role enums
        domain_roles = [
            role if isinstance(role, Role) else Role(role) 
            for role in roles_to_add
        ]

        # 3. Call domain method to mutate state
        account.add_roles(domain_roles)

        # 4. Persist updated domain model to database
        updated_account = await self.account_repo.update_roles(account)

        return updated_account


    async def remove_role(self, account_id: str, roles_to_remove: list[Role | str]) -> Account | None:
        # 1. Fetch account aggregate from repository
        account = await self.account_repo.find_by_id(account_id)
        if not account:
            raise AccountAccountNotFoundException(str(account_id))

        # 2. Normalize input roles to domain Role enums
        domain_roles = [
            role if isinstance(role, Role) else Role(role) 
            for role in roles_to_remove
        ]

        # 3. Call domain method to mutate state
        account.remove_roles(domain_roles)

        # 4. Persist updated domain model to database
        updated_account = await self.account_repo.update_roles(account)

        return updated_account
    
    async def switch_role(
        self, 
        account_id: str, 
        role: Role | str, 
        current_refresh_token: str | None = None
    ) -> dict[str, str] | None:
        # 1. Fetch account from repository
        account = await self.account_repo.find_by_id(account_id)
        if not account:
            raise AccountAccountNotFoundException(str(account_id))

        # Normalize role to domain Role enum if passed as string
        target_role = role if isinstance(role, Role) else Role(role)

        # 2. Safety Check: Verify role is actually in account's roles
        if target_role not in account.roles:
            raise RoleAssumingException(account_id, role)

        # 3. Mutate domain entity state
        account.switch_role(target_role)

        # 4. Persist updated domain model to DB using your repository method
        updated_account = await self.account_repo.update_active_role(account)

        # 5. Revoke current refresh token to enforce clean token rotation
        if current_refresh_token:
            await self.logout(current_refresh_token)

        # 6. Generate fresh JWT token pair reflecting the updated active_role
        return await self._generate_token_pair(updated_account)

    async def refresh_tokens(self, refresh_token: str) -> dict[str, str] | None:
        try:
            payload = jwt.decode(refresh_token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])

            if payload.get("type") != "refresh":
                raise InvalidJWTTokenException(reason=f"Refresh token '{refresh_token}' type is not refresh.")

            account_id = payload.get("sub")
            jti = payload.get("jti")

            if not account_id or not jti:
                raise InvalidJWTTokenException(reason=f"Refresh token '{refresh_token}' did not contain a valid account id and jti.")

            is_valid = await self.token_store.is_refresh_token_valid(account_id=account_id, jti=jti)
            if not is_valid:
                await self.token_store.revoke_all_account_tokens(account_id)
                raise InvalidJWTTokenException(reason=f"Refresh token '{refresh_token}' is not a valid refresh token.")

            # Revoke old refresh token
            await self.token_store.revoke_refresh_token(account_id=account_id, jti=jti)

            account = await self.account_repo.find_by_id(account_id)
            if not account:
                raise AccountAccountNotFoundException(account_id)

            return await self._generate_token_pair(account)

        except jwt.PyJWTError:
            raise InvalidJWTTokenException(reason=f"Refresh '{refresh_token} validation failed")

    async def logout(self, refresh_token: str) -> bool:
        try:
            payload = jwt.decode(refresh_token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
            account_id = payload.get("sub")
            jti = payload.get("jti")

            if not account_id or not jti:
                raise InvalidJWTTokenException(reason=f"Refresh token '{refresh_token}' did not contain a valid account id and jti.")
            
            await self.token_store.revoke_refresh_token(account_id=account_id, jti=jti)
            return True
        except jwt.PyJWTError:
            raise InvalidJWTTokenException(reason=f"Refresh '{refresh_token} validation failed")


    async def logout_all_devices(self, account_id: str) -> None:
        await self.token_store.revoke_all_account_tokens(account_id)

    # --- Helper Methods ---

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self.pwd_hash.verify(plain_password, hashed_password)

    def _create_token(self, payload: dict[str, Any], secret: str, expires_delta: timedelta) -> str:
        to_encode = payload.copy()
        now = datetime.now(timezone.utc)
        to_encode.update({"exp": now + expires_delta, "iat": now})
        return jwt.encode(to_encode, secret, algorithm=ALGORITHM)

    async def _generate_token_pair(self, account: Account, active_role: str | None = None) -> dict[str, str]:
        account_id_str = str(account.account_id)
        account_owner_id_str = str(account.owner_id)
        refresh_jti = str(uuid.uuid4())

        # Determine active role: use provided override, fall back to domain active_role, or grab first role string
        current_active_role = active_role or account.active_role.value

        # Normalize roles list for JWT payload (extract values if enum objects exist)
        roles_list = [role.value for role in account.roles]

        # 1. Access Token Payload
        access_payload = {
            "sub": account_id_str,
            "account_owner_id": account_owner_id_str,
            "email": account.email,
            "active_role": current_active_role,
            "roles": roles_list,
            "type": "access",
        }
        access_token = self._create_token(
            payload=access_payload,
            secret=SECRET_KEY,
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        # 2. Refresh Token Payload
        refresh_payload = {
            "sub": account_id_str,
            "jti": refresh_jti,
            "type": "refresh",
        }
        refresh_token = self._create_token(
            payload=refresh_payload,
            secret=REFRESH_SECRET_KEY,
            expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )

        # 3. Store the active refresh token's JTI
        ttl = int(timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS).total_seconds())
        await self.token_store.save_refresh_token(account_id=account_id_str, jti=refresh_jti, ttl_seconds=ttl)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }
