"""Engine construction, failure classification and the retry policy, for every context.

The part of the Postgres adapters that has no bounded context in it. Whether a dropped
connection is worth retrying is a fact about Postgres, not about admissions or billing, and
seven copies of that table would be seven chances for one of them to be subtly wrong about
SQLSTATE 40001.

**A flat module rather than a package, deliberately.** ``discover_contexts()`` in
``tests/architecture/test_dependency_rule.py`` finds bounded contexts by looking for
directories under ``src/`` that carry an ``__init__.py``. A package here would become an
eighth context: the fitness test's ``EXPECTED_CONTEXTS`` assertion would fail, and every
adapter importing it would read as a cross-context import. A module is none of those things,
and it is honest — this is infrastructure, not a context, and it holds no domain type.

What it deliberately does *not* hold is the translation into anybody's error vocabulary.
:func:`classify` says what kind of failure happened; turning ``Failure.DUPLICATE`` into
``admissions.ports.DuplicateAggregateError`` rather than
``billing.ports.DuplicateAggregateError`` is each context's own business, done in its own
``adapters/outbound/postgres/_errors.py``. That duplication is the one
``enrollment/ports/errors.py`` already argues for: "a context may not import another
context's code at all, and the duplication is the price of the boundary."

The resilience pattern is CLAUDE.md section 4's, point by point:

* **Retries with exponential backoff and jitter, at most 3 attempts** — :func:`resilient`,
  built on ``tenacity``.
* **Transient versus permanent matters.** Connection resets, deadlocks and serialisation
  failures are retried; a unique-constraint violation never is. Retrying a duplicate key
  would turn an answer into a delay: the second attempt fails for the same reason as the
  first, and the caller waits out the backoff to be told what was already known.
* **Explicit timeouts on every call** — a connect timeout and a server-side
  ``statement_timeout`` on the engine, and :func:`resilient` puts an ``asyncio.timeout``
  around each attempt so a connection that has stopped answering entirely cannot hang a
  request forever.
* **Port-level error types when retries are exhausted.** :class:`PersistenceUnavailableError`
  leaves here and becomes a ``PersistenceUnavailableError`` in the calling context, so no
  ``asyncpg`` or ``sqlalchemy`` exception ever reaches an application layer.

There is no circuit breaker, and its absence is not an oversight: section 4 asks for one on
"external gateway calls", and the database is not a third party. A breaker in front of the
only store the system has would convert a slow database into a system that has decided not
to try, which is not an improvement on a slow database.
"""

import asyncio
from collections.abc import Awaitable, Callable
from enum import Enum
from functools import wraps
from typing import ParamSpec, TypeVar

from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

DEFAULT_STATEMENT_TIMEOUT_MS = 5_000
"""How long one statement may run before Postgres cancels it.

Server-side, so it binds even if this process stops watching the clock. Generous for the
reads and single-row writes every repository here performs, and short enough that a request
waiting on a lock somebody forgot to commit fails rather than hangs.
"""

DEFAULT_CONNECT_TIMEOUT_S = 5.0
DEFAULT_OPERATION_TIMEOUT_S = 10.0
"""Ceiling for one attempt, including the time spent acquiring a connection from the pool.

Longer than the statement timeout on purpose: a statement that overruns should be cancelled
by Postgres with a diagnosable error, and this is the backstop for the case where nothing
comes back at all.
"""

MAX_ATTEMPTS = 3
"""CLAUDE.md section 4, by name: "max 3 attempts"."""


class Failure(Enum):
    """What kind of failure a driver exception is, as far as retrying is concerned."""

    TRANSIENT = "transient"
    """Worth trying again: the same call may well succeed on a healthy connection."""

    DUPLICATE = "duplicate"
    """A unique constraint refused the write. Permanent, and translated immediately."""

    PERMANENT = "permanent"
    """Anything else. Trying again would fail the same way and waste the backoff."""


TRANSIENT_SQLSTATES = frozenset(
    {
        "40001",  # serialization_failure — the retry this whole mechanism exists for
        "40P01",  # deadlock_detected — Postgres already picked a victim; be the one that retries
        "53300",  # too_many_connections
        "55P03",  # lock_not_available
        "57014",  # query_canceled — the statement timeout firing under momentary load
        "57P01",  # admin_shutdown
        "57P02",  # crash_shutdown
        "57P03",  # cannot_connect_now — the server is still starting
        "58030",  # io_error
        "08000",  # connection_exception
        "08003",  # connection_does_not_exist
        "08006",  # connection_failure
        "08001",  # sqlclient_unable_to_establish_sqlconnection
        "08004",  # sqlserver_rejected_establishment_of_sqlconnection
        "08007",  # transaction_resolution_unknown
    }
)

UNIQUE_VIOLATION = "23505"
"""The one permanent failure with a name of its own.

It is how a repository learns that ``add`` was called with an identifier already held, and
under a Postgres adapter it is *the* way to learn it: a read-then-write check would leave a
gap two concurrent callers can both pass through. The constraint answers the question
correctly and the classification carries the answer back.
"""


def classify(exc: BaseException) -> Failure:
    """Say whether ``exc`` is worth retrying.

    Reads the SQLSTATE off the driver exception rather than matching on message text, which
    is the gateway argument made about references: a string produced by somebody else's
    software is not a stable interface. ``asyncpg`` exposes ``sqlstate``; SQLAlchemy wraps
    them and keeps the original on ``orig``.

    Anything unrecognised is permanent. A failure nobody has classified is a failure nobody
    has established is safe to repeat, and retrying by default would mean writing twice on
    the strength of a guess.
    """
    sqlstate = _sqlstate_of(exc)
    if sqlstate == UNIQUE_VIOLATION:
        return Failure.DUPLICATE
    if sqlstate in TRANSIENT_SQLSTATES:
        return Failure.TRANSIENT
    if sqlstate is not None:
        return Failure.PERMANENT
    if isinstance(exc, TimeoutError | ConnectionError | OSError):
        return Failure.TRANSIENT
    if isinstance(exc, DBAPIError) and exc.connection_invalidated:
        return Failure.TRANSIENT
    return Failure.PERMANENT


def _sqlstate_of(exc: BaseException) -> str | None:
    """The SQLSTATE behind ``exc``, unwrapping SQLAlchemy's wrapper if there is one."""
    for candidate in (exc, getattr(exc, "orig", None)):
        if candidate is None:
            continue
        sqlstate = getattr(candidate, "sqlstate", None) or getattr(candidate, "pgcode", None)
        if isinstance(sqlstate, str):
            return sqlstate
    return None


class PersistenceUnavailableError(Exception):
    """Retries were exhausted, or the operation timed out. Never crosses a port as itself.

    Each context catches this and re-raises its own ``PersistenceUnavailableError``, which is
    what the ports' error modules mean by "a raw driver exception must never cross into the
    application layer".
    """


class _RetryableError(Exception):
    """Internal marker: the wrapped failure was classified as transient.

    Wrapping rather than matching on driver types keeps the retry predicate a single
    ``retry_if_exception_type`` instead of a second copy of :func:`classify`.
    """

    def __init__(self, cause: BaseException) -> None:
        super().__init__(str(cause))
        self.cause = cause


P = ParamSpec("P")
T = TypeVar("T")


def resilient(
    *,
    attempts: int = MAX_ATTEMPTS,
    timeout: float = DEFAULT_OPERATION_TIMEOUT_S,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Retry a repository operation on transient failures, and time each attempt out.

    Permanent failures — a unique violation above all — are re-raised on the first attempt
    with nothing waited out, which is the half of "transient vs permanent matters" that a
    blanket ``@retry`` gets wrong.

    The operation must be safe to run again. Every method decorated with this runs in one
    transaction that is rolled back before the next attempt, so a retry starts from the state
    the first attempt began in rather than half of its effects.
    """

    def decorate(operation: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(operation)
        async def run(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(attempts),
                    wait=wait_exponential_jitter(initial=0.05, max=1.0, jitter=0.05),
                    retry=retry_if_exception_type(_RetryableError),
                    reraise=False,
                ):
                    with attempt:
                        try:
                            async with asyncio.timeout(timeout):
                                return await operation(*args, **kwargs)
                        except (SQLAlchemyError, TimeoutError, OSError) as failure:
                            if classify(failure) is Failure.TRANSIENT:
                                raise _RetryableError(failure) from failure
                            raise
            except RetryError as exhausted:
                last = exhausted.last_attempt.exception()
                cause = last.cause if isinstance(last, _RetryableError) else last
                raise PersistenceUnavailableError(
                    f"{operation.__qualname__} failed after {attempts} attempts: {cause}"
                ) from cause
            raise AssertionError("unreachable: AsyncRetrying either returns or raises")

        return run

    return decorate


def engine_for(
    url: str,
    *,
    statement_timeout_ms: int = DEFAULT_STATEMENT_TIMEOUT_MS,
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT_S,
    echo: bool = False,
) -> AsyncEngine:
    """Build the engine every repository in every context shares.

    ``pool_pre_ping`` costs a round trip per checkout and buys the common case back: a
    connection the database closed while the process was idle is discovered and replaced
    rather than handed out to fail the next statement.
    """
    return create_async_engine(
        normalise_url(url),
        echo=echo,
        pool_pre_ping=True,
        connect_args={
            "timeout": connect_timeout,
            "server_settings": {"statement_timeout": str(statement_timeout_ms)},
        },
    )


def normalise_url(url: str) -> str:
    """Coerce a DSN to the async driver this system actually uses.

    ``.env.example`` and ``docker-compose.yaml`` both wrote ``postgresql+asyncpg://`` before
    any adapter existed, and a deployment is as likely to supply the bare ``postgresql://``
    that every other tool accepts. Fixing the scheme here means one place knows which driver
    is in use, rather than every caller having to.
    """
    for prefix in ("postgresql+psycopg://", "postgresql+psycopg2://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix) :]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url
