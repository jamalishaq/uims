"""The part of authentication that has no bounded context in it.

The token codec, the :class:`Principal` a decoded token becomes, and the FastAPI dependencies
every router guards itself with. Whether a missing bearer token is a 401 is a fact about HTTP,
not about admissions or billing, and eight copies of that decision would be eight chances for
one of them to answer 200.

**A flat module rather than a package, and not part of the identity context.** Both halves of
that matter:

- *Flat*, for ``http_api.py``'s reason stated at length in its own docstring —
  ``discover_contexts()`` in ``tests/architecture/test_dependency_rule.py`` finds bounded
  contexts by looking for directories under ``src/`` with an ``__init__.py``, so a package here
  would become a ninth context and every router importing it would read as a cross-context
  import.
- *Not identity*, which is the more interesting half. Every router in the system has to check
  a token. If that dependency lived in ``identity/``, Billing's router importing it would be a
  genuine cross-context import and rule (b) would reject it — rightly, because the rule is not
  a formality here: it is what stops seven contexts acquiring a compile-time dependency on an
  eighth.

So the system is split along the line that was already there. **Issuing** a token is a use
case — it happens after a password has been checked against a stored credential, which is
Identity's data and Identity's decision — and lives in ``identity/``. **Verifying** one is
transport: it reads a header, checks a signature, and produces a value object. That is this
module, and it imports no context at all.

The two ends share a vocabulary without sharing an import. :class:`Role` here restates
``identity.domain.values.Role``, and ``tests/identity/test_role_vocabulary_agrees.py`` asserts
the two are identical member-for-member. One shared enum would need either the domain importing
a flat module (rule (c): the domain layer is stdlib-only) or every context importing Identity
(rule (b)); two enums and an assertion is the cheaper price, and it is the arrangement
``tests/academic_records/domain/test_grading_scale.py`` already uses for the grading table.

``auth.md`` at the repository root records the decisions this module implements.
"""

import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Any

import jwt
from fastapi import Depends, FastAPI, Request

ACCESS_TOKEN = "access"
REFRESH_TOKEN = "refresh"
"""The ``typ`` claim's two values.

A refresh token presented as a bearer token is refused, and an access token presented to
``/auth/refresh`` is refused. Without the claim they would be interchangeable, and the 12-hour
lifetime chosen for one would silently become the lifetime of the other.
"""

ALGORITHM = "HS256"
MINIMUM_SECRET_BYTES = 32
"""RFC 7518 section 3.2: an HS256 key must be at least as long as the hash it produces.

Enforced rather than warned about. A shorter key does not fail — it signs and verifies
perfectly — which is exactly why a deployment would keep one forever. Refusing at startup makes
it a five-second fix in a ``.env`` file instead of a finding in an audit two years later.
"""

BEARER = "bearer"
STATE_KEY = "security"
"""Where the codec hangs on ``app.state``, set by the composition root."""


class Role(Enum):
    """The token's ``role`` claim, as the routers name it.

    A restatement of ``identity.domain.values.Role`` and asserted equal to it by a test — see
    this module's docstring on why it is a restatement rather than an import.
    """

    UNIVERSITY = "university"
    FACULTY = "faculty"
    DEPARTMENT = "department"
    LECTURER = "lecturer"
    STUDENT = "student"


class ScopeKind(Enum):
    """The token's ``scope_kind`` claim. Restates ``identity.domain.values.ScopeKind``."""

    UNIVERSITY = "university"
    FACULTY = "faculty"
    DEPARTMENT = "department"
    LECTURER = "lecturer"
    STUDENT = "student"


# ---- what goes wrong ----------------------------------------------------------------------


class SecurityError(Exception):
    """Base for every refusal this module makes."""


class AuthenticationRequiredError(SecurityError):
    """No usable bearer token was presented. A 401."""


class InvalidTokenError(AuthenticationRequiredError):
    """A token was presented and could not be trusted: bad signature, expired, wrong ``typ``.

    A subclass of :class:`AuthenticationRequiredError` rather than a sibling, because the
    client's remedy is the same in both cases — obtain a token — and the MRO walk in
    ``http_api._status_for`` then maps both to 401 from one entry.

    **The message never says which check failed.** "Signature invalid" and "expired" and "not
    an access token" are three different pieces of information about a token an attacker is
    holding, and a client that has a good token needs none of them.
    """


class ForbiddenError(SecurityError):
    """The caller is who they say they are and may not do this. A 403.

    Distinct from a 401 in the way that matters to a client: re-authenticating will not help.
    """


SECURITY_EXCEPTION_STATUSES: Mapping[type[Exception], int] = {
    AuthenticationRequiredError: 401,
    ForbiddenError: 403,
}
"""This module's exceptions, mapped to statuses, in the shape ``http_api`` installs.

:class:`InvalidTokenError` is absent on purpose: it inherits from
:class:`AuthenticationRequiredError`, and the MRO walk resolves it to the same 401. Listing it
would be restating the base for a subclass that agrees with it, which is the duplication
``http_api._status_for`` was written to avoid.
"""


# ---- who is calling -----------------------------------------------------------------------


@dataclass(frozen=True)
class Principal:
    """A verified caller: who they are, what kind of actor, and what they may reach.

    The whole of what a token carries, and deliberately less than a client might want. There is
    no name and no email here, for the reason CLAUDE.md section 6 gives for the identity context
    itself: a token holding a student's name would be a second place the university's record of
    who somebody is lives, and the two would drift. A client that wants a name asks the context
    that owns it, with the ``subject`` in hand.
    """

    subject: str
    """The principal id — a student id, a lecturer id, a department id. The ``sub`` claim."""

    login_id: str
    """What they typed. Carried for audit and for the client to display; never authorized on."""

    role: Role
    scope_kind: ScopeKind
    scope_id: str

    def covers(self, kind: ScopeKind, unit_id: str) -> bool:
        """Whether this principal's authority reaches ``(kind, unit_id)``.

        Restates ``identity.domain.values.Scope.covers`` and is asserted to agree with it by
        test, for this module's docstring's reason. A university scope covers everything; a
        faculty scope does *not* reach into its departments, because neither this module nor
        Identity holds the structure that would say which departments those are.
        """
        if self.scope_kind is ScopeKind.UNIVERSITY:
            return True
        return self.scope_kind is kind and self.scope_id == unit_id

    def require_scope(self, kind: ScopeKind, unit_id: str) -> None:
        """Raise :class:`ForbiddenError` unless this principal covers ``(kind, unit_id)``.

        The tier-2 check ``auth.md`` describes: the request named a unit, and the token is
        compared against it. Routes call this with a path parameter or a body field, never with
        something read off the token — a check comparing the token to itself always passes.
        """
        if not self.covers(kind, unit_id):
            raise ForbiddenError(
                f"{self.role.value} {self.login_id!r} is scoped to "
                f"{self.scope_kind.value} {self.scope_id!r} and may not act on "
                f"{kind.value} {unit_id!r}"
            )

    def require_self(self, unit_id: str) -> None:
        """Raise unless this principal *is* ``unit_id``, or is university-scoped.

        For the routes a person reads their own things through — a student's record, a
        lecturer's profile. Shorthand for :meth:`require_scope` against the principal's own
        scope kind, which for a student and a lecturer is themselves.
        """
        self.require_scope(self.scope_kind, unit_id)


# ---- the codec ----------------------------------------------------------------------------


class TokenCodec:
    """Signs and verifies the tokens. One instance per process, built by the composition root.

    The secret arrives as a constructor argument rather than being read here, which is the rule
    ``src/main.py`` states about itself: it is the only module in ``src/`` that reads
    ``os.environ``. That is also what lets a test pick its own signing key.
    """

    def __init__(
        self,
        secret: str,
        access_ttl_seconds: int = 30 * 60,
        refresh_ttl_seconds: int = 12 * 60 * 60,
        issuer: str = "ums",
    ) -> None:
        if not secret:
            raise ValueError("a signing secret is required; refusing to sign with an empty key")
        if len(secret.encode("utf-8")) < MINIMUM_SECRET_BYTES:
            raise ValueError(
                f"JWT_SECRET_KEY must be at least {MINIMUM_SECRET_BYTES} bytes for {ALGORITHM} "
                f"(RFC 7518 section 3.2); got {len(secret.encode('utf-8'))}"
            )
        self._secret = secret
        self.access_ttl_seconds = access_ttl_seconds
        self.refresh_ttl_seconds = refresh_ttl_seconds
        self._issuer = issuer

    def issue_access(self, principal: Principal, *, now: int | None = None) -> str:
        """A short-lived token for the ``Authorization`` header. 30 minutes by default."""
        return self._encode(principal, ACCESS_TOKEN, self.access_ttl_seconds, now)

    def issue_refresh(self, principal: Principal, *, now: int | None = None) -> str:
        """A longer-lived token for an ``HttpOnly`` cookie. 12 hours by default.

        **There is no server-side record of it**, so it cannot be revoked before it expires —
        recorded as an open decision in ``auth.md`` rather than quietly shipped as though a
        12-hour window were free. Logging out clears the cookie, which ends the session on that
        browser and not on a copy somebody else took.
        """
        return self._encode(principal, REFRESH_TOKEN, self.refresh_ttl_seconds, now)

    def decode(self, token: str, *, expected_type: str = ACCESS_TOKEN) -> Principal:
        """Verify a token and return who it says is calling.

        Raises :class:`InvalidTokenError` for every way this can fail — a bad signature, an
        expired token, a refresh token where an access token was wanted, a claim missing or
        holding a role this version does not know. One exception type and one message, because
        the differences between them are information about a token the caller is holding and
        the remedy is identical.
        """
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[ALGORITHM],
                issuer=self._issuer,
                options={"require": ["exp", "iat", "sub", "iss"]},
            )
        except jwt.PyJWTError as unusable:
            raise InvalidTokenError("the token could not be verified") from unusable

        if claims.get("typ") != expected_type:
            raise InvalidTokenError("the token could not be verified")
        try:
            return Principal(
                subject=str(claims["sub"]),
                login_id=str(claims["login_id"]),
                role=Role(claims["role"]),
                scope_kind=ScopeKind(claims["scope_kind"]),
                scope_id=str(claims["scope_id"]),
            )
        except (KeyError, ValueError) as unusable:
            raise InvalidTokenError("the token could not be verified") from unusable

    def _encode(
        self, principal: Principal, token_type: str, ttl_seconds: int, now: int | None
    ) -> str:
        issued_at = int(time.time()) if now is None else now
        claims: dict[str, Any] = {
            "sub": principal.subject,
            "login_id": principal.login_id,
            "role": principal.role.value,
            "scope_kind": principal.scope_kind.value,
            "scope_id": principal.scope_id,
            "typ": token_type,
            "iss": self._issuer,
            "iat": issued_at,
            "exp": issued_at + ttl_seconds,
        }
        return jwt.encode(claims, self._secret, algorithm=ALGORITHM)


# ---- the dependencies routers guard themselves with ----------------------------------------


def install_security(app: FastAPI, codec: TokenCodec) -> None:
    """Hand the codec to the app, where the request-time dependencies find it.

    ``app.state`` is the handover point for the same reason ``dependencies_of`` uses it: a
    dependency importing the composition root would be a cycle, since the root imports every
    router to mount it.
    """
    setattr(app.state, STATE_KEY, codec)


def codec_of(request: Request) -> TokenCodec:
    """The codec this app was built with."""
    codec = getattr(request.app.state, STATE_KEY, None)
    if not isinstance(codec, TokenCodec):
        raise RuntimeError(
            "no TokenCodec is wired at app.state.security; the composition root has not run. "
            "Refusing to serve a guarded route with no way to check a token."
        )
    return codec


def bearer_token(request: Request) -> str:
    """The token out of the ``Authorization`` header, or a 401.

    Case-insensitive on the scheme, because ``Bearer`` and ``bearer`` are the same header to
    every RFC and to nobody's client library.
    """
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != BEARER or not token.strip():
        raise AuthenticationRequiredError("this route needs a bearer token")
    return token.strip()


def current_principal(request: Request) -> Principal:
    """Who is calling. The dependency behind every guard below."""
    return codec_of(request).decode(bearer_token(request))


Authenticated = Annotated[Principal, Depends(current_principal)]
"""Any valid access token. The weakest guard, and never the only one on a write route."""


def requires(*roles: Role) -> Callable[[Request], Principal]:
    """A dependency admitting only these roles. The tier-1 gate ``auth.md`` describes.

    Static: it answers from the token alone and reads nothing. What it cannot do is decide
    *which* department a department registrar may act on — that is the tier-2 check, and it is
    the route's to make with :meth:`Principal.require_scope`, because only the route knows which
    of its parameters names a scope.

    ``requires()`` with no roles is a programming error rather than a permissive default: a
    guard that admitted everybody would look exactly like a guard.
    """
    if not roles:
        raise ValueError("requires() needs at least one role; use Authenticated for any caller")
    permitted = frozenset(roles)

    def guard(request: Request) -> Principal:
        principal = current_principal(request)
        if principal.role not in permitted:
            raise ForbiddenError(
                f"this route is for {_english(permitted)}; "
                f"{principal.login_id!r} is a {principal.role.value}"
            )
        return principal

    return guard


def _english(roles: Iterable[Role]) -> str:
    names = sorted(role.value for role in roles)
    if len(names) == 1:
        return f"a {names[0]}"
    return f"{', '.join(names[:-1])} or {names[-1]}"


University = Annotated[Principal, Depends(requires(Role.UNIVERSITY))]
"""The bursary and the registry, acting university-wide. Section 6's bursar."""

Faculty = Annotated[Principal, Depends(requires(Role.FACULTY, Role.UNIVERSITY))]
"""A faculty officer, or the university above them."""

Department = Annotated[Principal, Depends(requires(Role.DEPARTMENT, Role.UNIVERSITY))]
"""A department registrar, or the university above them."""

Lecturer = Annotated[Principal, Depends(requires(Role.LECTURER))]
"""A lecturer, and nobody above them.

The one guard with no university fallback, and the omission is deliberate: submitting a grade
is a lecturer acting on their own course, and the domain check behind it
(``GradeSubmission.submit()`` asking ``lecturer.is_assigned_to(course)``) has no meaning for a
principal that is not a lecturer. A university-scoped caller admitted here would reach a
refusal it could never satisfy, which is a worse answer than the 403 it gets instead.
"""

Student = Annotated[Principal, Depends(requires(Role.STUDENT, Role.UNIVERSITY))]
"""A student reading their own things, or the university reading anybody's."""

Staff = Annotated[Principal, Depends(requires(Role.UNIVERSITY, Role.FACULTY, Role.DEPARTMENT))]
"""Anybody who administers something. For reads a student has no business making."""


__all__ = [
    "ACCESS_TOKEN",
    "REFRESH_TOKEN",
    "SECURITY_EXCEPTION_STATUSES",
    "STATE_KEY",
    "Authenticated",
    "AuthenticationRequiredError",
    "Department",
    "Faculty",
    "ForbiddenError",
    "InvalidTokenError",
    "Lecturer",
    "Principal",
    "Role",
    "ScopeKind",
    "SecurityError",
    "Staff",
    "Student",
    "TokenCodec",
    "University",
    "bearer_token",
    "codec_of",
    "current_principal",
    "install_security",
    "requires",
]
