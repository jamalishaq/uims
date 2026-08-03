"""Turning a driver failure into something this context is allowed to say.

``ports/errors.py`` promises that "a unique-constraint violation becomes
:class:`DuplicateAggregateError` here rather than surfacing as ``psycopg.IntegrityError``".
This is where that promise is kept, and it is the whole of what is context-specific about the
Postgres adapters: ``persistence.classify`` decides *what kind* of failure happened, and this
module decides what Faculty & Department calls it.

Duplicated in each of the seven contexts, for the reason ``enrollment/ports/errors.py``
already gives about its own copy of those three names: "a context may not import another
context's code at all, and the duplication is the price of the boundary". Two contexts
agreeing today about what a duplicate is does not mean they must agree forever.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.exc import SQLAlchemyError

from faculty_department.ports.errors import (
    DuplicateAggregateError,
    PersistenceUnavailableError,
    RepositoryError,
)
from persistence import Failure, classify
from persistence import PersistenceUnavailableError as Unavailable


@asynccontextmanager
async def translating(what: str) -> AsyncIterator[None]:
    """Re-raise whatever the driver says as something this context's callers can catch.

    ``what`` names the aggregate and identifier so the message says which write failed —
    "faculty fac-sci is already stored" reads the way the in-memory adapter's does, which
    matters because the same tests assert against both.
    """
    try:
        yield
    except Unavailable as exhausted:
        raise PersistenceUnavailableError(
            f"the store could not be reached while working with {what}"
        ) from exhausted
    except SQLAlchemyError as failure:
        if classify(failure) is Failure.DUPLICATE:
            raise DuplicateAggregateError(f"{what} is already stored") from failure
        raise RepositoryError(f"the store refused an operation on {what}") from failure
