"""Creating, disabling and re-passwording credentials: the administrative half.

Everything here is university-scoped work. Nothing in this module is reachable by the principal
it acts on, with the single exception of :class:`ChangePassword`, which is the one act somebody
performs on themselves.
"""

from dataclasses import dataclass

from identity.application.errors import (
    CredentialNotFoundError,
    LoginIdAlreadyIssuedError,
    PrincipalAlreadyHasCredentialError,
    UnknownRoleError,
)
from identity.domain.credential import Credential
from identity.domain.errors import IdentityError
from identity.domain.values import Role
from identity.ports.credential_repository import CredentialRepositoryPort


@dataclass(frozen=True)
class IssueCredentialCommand:
    """Everything needed to make one login work.

    ``scope_unit_id`` defaults to ``principal_id`` because for four of the five roles they are
    the same value — a department's credential is scoped to that department, a lecturer's to
    themselves. Only a login whose principal and scope genuinely differ has to say so, which is
    the shape a named office-holder would take.
    """

    login_id: str
    principal_id: str
    role: str
    password: str
    credential_id: str | None = None
    scope_unit_id: str | None = None

    def parsed_role(self) -> Role:
        """The role as the domain's enum, or a refusal naming what was allowed.

        The command carries a **string** because the route that fills it may not name a domain
        type — rule (d) of the fitness test — and translating the wire's vocabulary into the
        domain's is the application layer's job rather than the transport's. Pydantic could have
        been given an enum of its own, and then there would be three role vocabularies to keep
        in step instead of two.
        """
        try:
            return Role(self.role)
        except ValueError as unknown:
            permitted = ", ".join(sorted(role.value for role in Role))
            raise UnknownRoleError(
                f"{self.role!r} is not a role; expected one of {permitted}"
            ) from unknown


class IssueCredential:
    """Create a credential, refusing the two collisions that would create a second password.

    Both checks are made here rather than left to the repository's unique constraints, and the
    reason is that they mean different things to a caller. A duplicate *login id* is somebody
    else's account — pick another name. A duplicate *principal* is this same person already
    having a login, and creating a second would leave two live passwords for one lecturer with
    no way to tell which one they are using and no way to retire the other.

    The constraints stay in the schema regardless: these checks are not atomic against a
    concurrent caller, so they are the *message*, and the index is the guarantee.
    """

    def __init__(self, credentials: CredentialRepositoryPort) -> None:
        self._credentials = credentials

    async def execute(self, command: IssueCredentialCommand) -> Credential:
        role = command.parsed_role()
        if await self._credentials.find_by_login_id(command.login_id) is not None:
            raise LoginIdAlreadyIssuedError(f"login id {command.login_id!r} is already in use")
        if await self._credentials.find_by_principal(command.principal_id) is not None:
            raise PrincipalAlreadyHasCredentialError(
                f"principal {command.principal_id!r} already has a credential; "
                f"reset its password rather than issuing a second one"
            )

        credential = Credential.issue(
            credential_id=command.credential_id or f"CRED-{command.principal_id}",
            login_id=command.login_id,
            principal_id=command.principal_id,
            role=role,
            scope_unit_id=command.scope_unit_id or command.principal_id,
            password=command.password,
        )
        await self._credentials.add(credential)
        return credential


@dataclass(frozen=True)
class ChangePasswordCommand:
    """A principal replacing their own password.

    ``current_password`` is required and checked. An administrator resetting a password somebody
    has forgotten uses :class:`ResetPassword` instead — the two are separate use cases because
    they answer "may you do this?" in genuinely different ways, and one method taking an
    optional old password would let the administrative path be reached by omitting a field.
    """

    login_id: str
    current_password: str
    new_password: str


class ChangePassword:
    """Replace a password, having proved the old one.

    Raises :class:`CredentialNotFoundError` for an unknown login id rather than the login flow's
    deliberately-vague refusal. It is not an enumeration oracle here: reaching this use case
    already required an access token, and a caller may only change *their own* password — the
    route checks the login id against the token before this runs.
    """

    def __init__(self, credentials: CredentialRepositoryPort) -> None:
        self._credentials = credentials

    async def execute(self, command: ChangePasswordCommand) -> Credential:
        credential = await self._credentials.find_by_login_id(command.login_id)
        if credential is None:
            raise CredentialNotFoundError(f"no credential with login id {command.login_id!r}")
        if not credential.authenticate(command.current_password):
            raise IdentityError("current password is incorrect")
        credential.change_password(command.new_password)
        await self._credentials.save(credential)
        return credential


@dataclass(frozen=True)
class ResetPasswordCommand:
    """An administrator setting a password for somebody who cannot supply their old one."""

    login_id: str
    new_password: str


class ResetPassword:
    """Set a password without the old one. University-scoped; the route enforces that."""

    def __init__(self, credentials: CredentialRepositoryPort) -> None:
        self._credentials = credentials

    async def execute(self, command: ResetPasswordCommand) -> Credential:
        credential = await self._credentials.find_by_login_id(command.login_id)
        if credential is None:
            raise CredentialNotFoundError(f"no credential with login id {command.login_id!r}")
        credential.change_password(command.new_password)
        await self._credentials.save(credential)
        return credential


@dataclass(frozen=True)
class SetCredentialActiveCommand:
    """Turn a login on or off."""

    login_id: str
    is_active: bool


class SetCredentialActive:
    """Deactivate or reactivate a credential.

    Deactivating does not delete. A login id freed for reissue is a login id that once meant one
    principal and now means another, and an audit trail with one of those in it has stopped
    being evidence.

    **It does not end a session already in flight.** An access token already issued stays valid
    for up to thirty minutes; the refresh path re-reads the credential and refuses from then on.
    That is the bound this system offers and ``auth.md`` says so plainly rather than implying
    that deactivation is immediate.
    """

    def __init__(self, credentials: CredentialRepositoryPort) -> None:
        self._credentials = credentials

    async def execute(self, command: SetCredentialActiveCommand) -> Credential:
        credential = await self._credentials.find_by_login_id(command.login_id)
        if credential is None:
            raise CredentialNotFoundError(f"no credential with login id {command.login_id!r}")
        credential.reactivate() if command.is_active else credential.deactivate()
        await self._credentials.save(credential)
        return credential


class ReadPrincipal:
    """Who a login id or a principal id belongs to.

    ``find`` answers ``None`` rather than raising, in the manner of ``ReadAccount.find`` and
    ``ReadStudent.find``: absence is a normal answer to a question about an identifier a caller
    was handed by somebody else.
    """

    def __init__(self, credentials: CredentialRepositoryPort) -> None:
        self._credentials = credentials

    async def find_by_login_id(self, login_id: str) -> Credential | None:
        return await self._credentials.find_by_login_id(login_id)

    async def find_by_principal(self, principal_id: str) -> Credential | None:
        return await self._credentials.find_by_principal(principal_id)

    async def all(self) -> list[Credential]:
        """Every credential. The administrative list, and never part of a login flow."""
        return await self._credentials.all()
