"""Roles, scopes and password hashes: everything a credential is made of but its identity.

Two of these are worth reading before the aggregate. :class:`Role` and :class:`ScopeKind` are
the vocabulary the whole system's authorization is written in, and :class:`PasswordHash` is the
one value object in this repository with a security property to keep.
"""

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass
from enum import Enum

from identity.domain.errors import (
    InvalidLoginIdError,
    InvalidPasswordError,
    InvalidPasswordHashError,
    InvalidScopeError,
    MissingIdentifierError,
)

MINIMUM_PASSWORD_LENGTH = 8
"""Short, and on purpose.

A length floor is the only password-quality rule here. Composition rules — a digit, a symbol,
a capital — are the ones that reliably produce ``Password1!`` and a sticky note, and choosing
them for a real university is an institutional decision nobody has made (CLAUDE.md section 6).
Eight is the floor below which a hash is worth brute-forcing regardless of policy.
"""

_SCRYPT_N = 16384
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_KEY_BYTES = 32
_ALGORITHM = "scrypt"
_FIELD_SEPARATOR = "$"
_HASH_FIELDS = 6


def require_identifier(value: str, field: str) -> str:
    """Return ``value`` stripped, rejecting anything blank.

    The same guard four other contexts write for themselves, duplicated here for the reason
    ``student_profile/domain/values.py`` states: a context may not import another's domain, and
    two contexts agreeing today about what a blank identifier is does not mean they must agree
    forever.
    """
    if not isinstance(value, str) or not value.strip():
        raise MissingIdentifierError(f"{field} must be a non-empty identifier")
    return value.strip()


class Role(Enum):
    """What kind of actor a credential belongs to.

    Five, and they are the actors CLAUDE.md section 6 confirmed with a human — a department
    registrar, a faculty officer, a bursar, a lecturer and a student — with one renaming: the
    bursar is ``UNIVERSITY``. Section 6 describes the bursar as "university-scoped: fee
    schedules, session fees, reconciliation, ledger reads", which is the university's reach
    exactly. A separate ``BURSAR`` member would be a second name for one set of permissions,
    and two names for one thing is how they start to disagree about what they cover.

    **The values are the wire format**: they are what a token's ``role`` claim carries and what
    ``security.Role`` restates for the routers to guard against. The two enums are asserted
    equal by ``tests/identity/test_role_vocabulary_agrees_with_security.py``, because the
    alternative — one shared enum — needs either the domain importing a flat module (rule (c):
    the domain layer is stdlib-only) or every context importing this one (rule (b)).
    """

    UNIVERSITY = "university"
    FACULTY = "faculty"
    DEPARTMENT = "department"
    LECTURER = "lecturer"
    STUDENT = "student"

    @property
    def scope_kind(self) -> "ScopeKind":
        """The kind of thing a credential in this role is always scoped to.

        A role and its scope kind are not independent: a ``FACULTY`` credential scoped to a
        student would be a combination no part of the system knows how to check. Deriving one
        from the other rather than storing both is what makes that combination unconstructible
        instead of merely unlikely.
        """
        return _SCOPE_KIND_FOR_ROLE[self]


class ScopeKind(Enum):
    """The kind of unit a credential's authority is bounded by.

    "A registrar's permission is meaningless without *which department*" — section 6. This is
    the *which* half's type; :class:`Scope` carries the id.

    ``SELF`` is not a member and that is deliberate. A lecturer and a student are both scoped
    to themselves, but a route comparing a token's scope against a path parameter has to know
    *which* self — a lecturer id and a student id are minted by different contexts and are not
    interchangeable — so they are two kinds rather than one.
    """

    UNIVERSITY = "university"
    FACULTY = "faculty"
    DEPARTMENT = "department"
    LECTURER = "lecturer"
    STUDENT = "student"


_SCOPE_KIND_FOR_ROLE = {
    Role.UNIVERSITY: ScopeKind.UNIVERSITY,
    Role.FACULTY: ScopeKind.FACULTY,
    Role.DEPARTMENT: ScopeKind.DEPARTMENT,
    Role.LECTURER: ScopeKind.LECTURER,
    Role.STUDENT: ScopeKind.STUDENT,
}
"""One entry per role, checked exhaustive by a test rather than trusted.

Written as a module-level table rather than a ``match`` inside the property so that a role
added without a scope kind fails loudly on the next lookup instead of falling through a
default.
"""


@dataclass(frozen=True)
class Scope:
    """What a credential may reach: a kind, and the id of one unit of that kind.

    ``Scope(ScopeKind.DEPARTMENT, "DEPT-CSC")`` — the department registrar for Computer
    Science, and nobody else's registrar.
    """

    kind: ScopeKind
    unit_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ScopeKind):
            raise InvalidScopeError("scope kind must be a ScopeKind")
        object.__setattr__(self, "unit_id", require_identifier(self.unit_id, "scope unit id"))

    def covers(self, kind: "ScopeKind", unit_id: str) -> bool:
        """Whether a request naming ``(kind, unit_id)`` falls inside this scope.

        **A university scope covers everything.** That is what university-scoped means, and it
        is the only widening rule in the system: a faculty scope does *not* cover the
        departments inside it here, because this context does not hold the faculty→department
        structure and inventing it would make Identity the second place that structure lives —
        the exact failure the context was carved out to avoid.

        The consequence is that a ``faculty`` token cannot be checked against a department id
        by this method, and no route asks it to. Where a faculty officer acts on a department
        the request names the *faculty* (``POST /departments`` carries ``faculty_id`` in its
        body), which is the shape section 6 asked for in advance: scope travels as an explicit
        parameter, so a token constrains a filter rather than supplying an identity.
        """
        if self.kind is ScopeKind.UNIVERSITY:
            return True
        return self.kind is kind and self.unit_id == unit_id

    def __str__(self) -> str:
        return f"{self.kind.value}:{self.unit_id}"


@dataclass(frozen=True)
class PasswordHash:
    """A password, as the only form of it this system is ever allowed to hold.

    ``scrypt$16384$8$1$<salt-b64>$<key-b64>``. The cost parameters live *inside* the string
    rather than in a constant the verifier reads, so raising them later re-hashes each
    credential on its next successful login instead of invalidating every credential at once.

    **Why scrypt and not bcrypt or argon2.** This is a value object in ``domain/``, where rule
    (c) of the fitness test permits the standard library and nothing else. A ``PasswordHash``
    that could not hash its own password would have to hand the plaintext outward to something
    that could, and outward is the one direction a plaintext password must never travel. The
    stdlib offers a memory-hard KDF, which is the property that actually matters here; the
    dependency would have bought a nicer API and a worse boundary.

    The plaintext is never stored, never logged, and never an attribute. :meth:`verify`
    compares with :func:`hmac.compare_digest` so that a wrong password takes the same time to
    reject however much of it was right.
    """

    encoded: str

    def __post_init__(self) -> None:
        if not isinstance(self.encoded, str) or not self.encoded:
            raise InvalidPasswordHashError("password hash must be a non-empty string")
        algorithm, n, r, p, salt, key = self._fields(self.encoded)
        if algorithm != _ALGORITHM:
            raise InvalidPasswordHashError(f"unsupported password hash algorithm {algorithm!r}")
        for name, raw in (("n", n), ("r", r), ("p", p)):
            if not raw.isdigit() or int(raw) < 1:
                raise InvalidPasswordHashError(f"scrypt parameter {name} is not a positive integer")
        for name, raw in (("salt", salt), ("key", key)):
            try:
                base64.urlsafe_b64decode(raw)
            except (ValueError, TypeError) as unreadable:
                raise InvalidPasswordHashError(f"scrypt {name} is not valid base64") from unreadable

    @staticmethod
    def _fields(encoded: str) -> list[str]:
        fields = encoded.split(_FIELD_SEPARATOR)
        if len(fields) != _HASH_FIELDS:
            raise InvalidPasswordHashError(
                f"password hash must have {_HASH_FIELDS} {_FIELD_SEPARATOR}-separated fields"
            )
        return fields

    @classmethod
    def of(cls, plaintext: str) -> "PasswordHash":
        """Hash a new password, rejecting one too short to be worth hashing.

        The salt is 16 bytes from :func:`os.urandom` — per credential, never derived from the
        login id. A salt derived from something a caller knows would let one precomputed table
        serve every credential that shares it.
        """
        require_password(plaintext)
        salt = os.urandom(_SALT_BYTES)
        key = cls._derive(plaintext, salt, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P)
        return cls(
            _FIELD_SEPARATOR.join(
                (
                    _ALGORITHM,
                    str(_SCRYPT_N),
                    str(_SCRYPT_R),
                    str(_SCRYPT_P),
                    _b64(salt),
                    _b64(key),
                )
            )
        )

    def verify(self, plaintext: str) -> bool:
        """Whether ``plaintext`` is the password this hash was made from.

        Answers ``False`` rather than raising for a plaintext that could never have been
        hashed — too short, or not a string at all. A caller checking a password is asking a
        yes/no question, and an exception on some wrong answers and ``False`` on others would
        be an oracle telling an attacker which kind of wrong they got.
        """
        if not isinstance(plaintext, str):
            return False
        _, n, r, p, salt, key = self._fields(self.encoded)
        try:
            candidate = self._derive(
                plaintext, base64.urlsafe_b64decode(salt), int(n), int(r), int(p)
            )
        except (ValueError, MemoryError):
            return False
        return hmac.compare_digest(candidate, base64.urlsafe_b64decode(key))

    @property
    def needs_rehash(self) -> bool:
        """Whether this hash was made with weaker parameters than the current ones.

        What makes the cost parameters worth storing in the string. A credential answering
        ``True`` is re-hashed on its next successful login, when the plaintext is briefly and
        legitimately in hand — the only moment it can be, and the reason this is a property
        rather than a background job.
        """
        _, n, r, p, _, _ = self._fields(self.encoded)
        return (int(n), int(r), int(p)) != (_SCRYPT_N, _SCRYPT_R, _SCRYPT_P)

    @staticmethod
    def _derive(plaintext: str, salt: bytes, n: int, r: int, p: int) -> bytes:
        return hashlib.scrypt(plaintext.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=_KEY_BYTES)

    def __repr__(self) -> str:
        """Never the hash itself.

        A hash in a log line or a traceback is an offline attack somebody else gets to run at
        their leisure, and the default dataclass ``__repr__`` would put it in both.
        """
        return "PasswordHash(<redacted>)"

    def __str__(self) -> str:
        return repr(self)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii")


def require_password(plaintext: str) -> str:
    """Return ``plaintext`` unchanged, rejecting one too short to hash.

    Deliberately does not strip. A leading space in a password is a character the person typed
    and will type again; stripping it here would silently let a different password in.
    """
    if not isinstance(plaintext, str):
        raise InvalidPasswordError("password must be a string")
    if len(plaintext) < MINIMUM_PASSWORD_LENGTH:
        raise InvalidPasswordError(
            f"password must be at least {MINIMUM_PASSWORD_LENGTH} characters"
        )
    return plaintext


def require_login_id(value: str) -> str:
    """Return the login id stripped, rejecting blanks and anything with inner whitespace.

    Surrounding whitespace is stripped because it is what a paste or an autofill adds and never
    what somebody meant. Inner whitespace is refused because a login id is matched exactly, and
    ``DEPT CSC`` failing to match ``DEPT  CSC`` is a support ticket nobody can diagnose from a
    log line.
    """
    stripped = require_identifier(value, "login id")
    if any(character.isspace() for character in stripped):
        raise InvalidLoginIdError(f"login id {value!r} may not contain whitespace")
    return stripped
