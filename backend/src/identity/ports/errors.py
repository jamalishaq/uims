"""Failures a repository or issuer port is allowed to express.

The same four types the other seven contexts each declare for themselves, duplicated here for
the reason ``student_profile/ports/errors.py`` states: a context may not import another's, and
a raw driver exception must never cross into the application layer.

Absence is deliberately not one of them. ``find_by_login_id`` returns ``None`` for a login id
nobody holds, because somebody typing a wrong username is a normal answer and not a failure —
and, importantly, it is the *same* answer as a right username with a wrong password by the time
it reaches a client. See ``application/errors.py``.
"""


class RepositoryError(Exception):
    """Base class for every failure a port in this context can raise."""


class DuplicateAggregateError(RepositoryError):
    """``add`` was called with a credential id, or a login id, the repository already holds.

    Covers both keys, because both are unique and a caller can do nothing different about
    either: a login id already taken and a credential id already taken are the same instruction
    to pick another.
    """


class AggregateNotFoundError(RepositoryError):
    """``save`` was called with a credential id the repository never held."""


class PersistenceUnavailableError(RepositoryError):
    """The store could not be reached, and retrying did not help."""


class TokenIssuanceError(RepositoryError):
    """A token could not be signed.

    In practice a misconfigured signing key, which ``TokenCodec`` refuses at construction — so
    this is the failure that should be unreachable in a process that started. It exists because
    the port may not leak a ``jwt.PyJWTError`` into the application layer any more than an
    adapter may leak an ``asyncpg`` one.
    """
