"""The ``Credential`` aggregate: one login, and everything authorization needs to decide.

Deliberately the whole of this context's model. There is no ``User``, no ``Person``, no
``Profile`` — CLAUDE.md section 6 says this context holds "credentials, role and scope only —
never names or bio-data", and a second entity here would be the first step towards the second
identity system it warns against.
"""

from dataclasses import dataclass

from identity.domain.errors import CredentialInactiveError, InvalidScopeError
from identity.domain.values import (
    PasswordHash,
    Role,
    Scope,
    ScopeKind,
    require_identifier,
    require_login_id,
)


@dataclass
class Credential:
    """A login id, the hash of its password, and the authority it carries.

    Four identifiers appear here and they are not the same thing, which is the reason the class
    is worth reading slowly:

    - ``credential_id`` — this context's own storage key. Nobody outside ever quotes it.
    - ``login_id`` — what a person types. For a student it is their **matric number**; for a
      department it is the department's own id. Unique across the system.
    - ``principal_id`` — the id of the thing being logged in as, minted by whichever context
      owns it: Student Profile's ``student_id``, Faculty & Department's ``lecturer_id`` or
      ``department_id``. It is what a token's ``sub`` claim carries and what a scope check
      compares against a path parameter.
    - ``scope.unit_id`` — the unit the authority is bounded by.

    For a lecturer and a student, ``principal_id`` and ``scope.unit_id`` are the same value —
    they are scoped to themselves. For a department they are also the same, because the
    principal *is* the unit. They are kept as separate fields anyway, because the day a named
    office-holder is issued a credential (``a.adeyemi`` acting as the Computer Science
    registrar) the two stop being equal, and a model that had conflated them would have to be
    migrated rather than extended. ``auth.md`` records that as the intended growth path.

    **This aggregate never sees a plaintext password except to check or replace one**, and both
    of those hand it straight to :class:`PasswordHash` without storing it.
    """

    credential_id: str
    login_id: str
    principal_id: str
    role: Role
    scope: Scope
    password_hash: PasswordHash
    is_active: bool = True

    def __post_init__(self) -> None:
        self.credential_id = require_identifier(self.credential_id, "credential id")
        self.login_id = require_login_id(self.login_id)
        self.principal_id = require_identifier(self.principal_id, "principal id")
        if not isinstance(self.role, Role):
            raise InvalidScopeError("role must be a Role")
        if not isinstance(self.scope, Scope):
            raise InvalidScopeError("scope must be a Scope")
        if not isinstance(self.password_hash, PasswordHash):
            raise InvalidScopeError("password hash must be a PasswordHash")
        if self.scope.kind is not self.role.scope_kind:
            raise InvalidScopeError(
                f"a {self.role.value} credential is scoped to a "
                f"{self.role.scope_kind.value}, not a {self.scope.kind.value}"
            )
        if not isinstance(self.is_active, bool):
            raise InvalidScopeError("is_active must be a boolean")

    @classmethod
    def issue(
        cls,
        credential_id: str,
        login_id: str,
        principal_id: str,
        role: Role,
        scope_unit_id: str,
        password: str,
    ) -> "Credential":
        """Create an active credential, hashing the password on the way in.

        The scope's *kind* is not an argument: it is derived from the role, so a faculty
        credential scoped to a student is not a combination a caller can ask for and then be
        refused — it is one that cannot be expressed.

        The role is checked here rather than left to ``__post_init__``, because deriving the
        scope kind from it happens first and a string would fail as an ``AttributeError`` —
        a wrong-type argument reported as a bug in this method rather than in the call.
        """
        if not isinstance(role, Role):
            raise InvalidScopeError("role must be a Role")
        return cls(
            credential_id=credential_id,
            login_id=login_id,
            principal_id=principal_id,
            role=role,
            scope=Scope(kind=role.scope_kind, unit_id=scope_unit_id),
            password_hash=PasswordHash.of(password),
        )

    @classmethod
    def restore(
        cls,
        credential_id: str,
        login_id: str,
        principal_id: str,
        role: Role,
        scope: Scope,
        password_hash: PasswordHash,
        is_active: bool,
    ) -> "Credential":
        """Rebuild a stored credential. A persistence adapter is the only caller.

        Present for the reason CLAUDE.md section 4 gives for the six aggregates that have one:
        ``is_active`` is reachable only through :meth:`deactivate`, and a repository setting it
        through a private attribute would skip the validation in ``__post_init__`` — including
        the role/scope agreement, which is the check that stops a row nobody can authorize from
        becoming a credential that authorizes everything.

        Unlike the other six there are no transitions to re-run here, so this is a plain
        construction. It exists to be the *named* door rather than to do extra work, so that
        "reconstitution goes through ``restore``" stays true of every aggregate in the system
        and a reader does not have to check which ones mean it.
        """
        return cls(
            credential_id=credential_id,
            login_id=login_id,
            principal_id=principal_id,
            role=role,
            scope=scope,
            password_hash=password_hash,
            is_active=is_active,
        )

    def authenticate(self, password: str) -> bool:
        """Whether this password is the right one for an active credential.

        Raises for a deactivated credential rather than answering ``False``, because the two
        are different facts and the caller is the only one that can decide whether to tell them
        apart. ``application/authenticate.py`` decides not to — see its docstring on why the
        wire answer is one message for both.
        """
        if not self.is_active:
            raise CredentialInactiveError(f"credential {self.login_id!r} is not active")
        return self.password_hash.verify(password)

    def change_password(self, new_password: str) -> None:
        """Replace the password. Refuses on a deactivated credential.

        Takes no old password: whether the caller has proved they may do this is the use case's
        question, and it has two right answers — a person changing their own password proves it
        by knowing the old one, an administrator resetting a forgotten one cannot. An aggregate
        demanding the old one would make the second case impossible; one checking a role would
        be an aggregate reading a permission it does not hold.
        """
        if not self.is_active:
            raise CredentialInactiveError(
                f"credential {self.login_id!r} is not active and cannot change its password"
            )
        self.password_hash = PasswordHash.of(new_password)

    def rehash(self, password: str) -> None:
        """Re-derive the hash under the current cost parameters.

        Called only just after :meth:`authenticate` has answered ``True`` for this same
        plaintext, which is the one moment the plaintext is legitimately in hand. It is a
        separate method from :meth:`change_password` because the password is not changing and
        a caller reading ``change_password`` in a login flow would reasonably think it had.
        """
        if self.password_hash.needs_rehash:
            self.password_hash = PasswordHash.of(password)

    def deactivate(self) -> None:
        """Stop this credential working, without deleting what it was.

        Idempotent. Deleting the row instead would free the login id for reissue, and a login
        id that once meant one principal and now means another is how an audit trail stops
        being evidence.
        """
        self.is_active = False

    def reactivate(self) -> None:
        """Undo a deactivation. Idempotent."""
        self.is_active = True

    def covers(self, kind: ScopeKind, unit_id: str) -> bool:
        """Whether this credential's authority reaches ``(kind, unit_id)``."""
        return self.scope.covers(kind, unit_id)

    def __repr__(self) -> str:
        """Without the hash, for :meth:`PasswordHash.__repr__`'s reason."""
        return (
            f"Credential(credential_id={self.credential_id!r}, login_id={self.login_id!r}, "
            f"principal_id={self.principal_id!r}, role={self.role!r}, scope={self.scope!r}, "
            f"is_active={self.is_active!r})"
        )
