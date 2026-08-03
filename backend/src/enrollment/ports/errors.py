"""Failures a repository port is allowed to express.

These are the types an adapter translates *into*. Per CLAUDE.md section 4, a raw driver
exception must never cross into the application layer: when the Postgres adapters arrive
in Phase 6, a unique-constraint violation becomes :class:`DuplicateAggregateError` here
rather than surfacing as ``psycopg.IntegrityError``. The application layer is written
against this vocabulary from the start, so that swap changes no calling code.

Absence is deliberately *not* one of these. ``get`` returns ``None`` for an id nobody
stored: not finding something you asked about is a normal answer, not a failure.

A per-context copy of the same three names Admissions, Course Catalog and the rest each
hold. A context may not import another context's code at all, and the duplication is the
price of the boundary — one this context may yet spend, since a registration repository
under load has failure modes an admissions one does not.
"""


class RepositoryError(Exception):
    """Base class for every failure a repository port can raise."""


class DuplicateAggregateError(RepositoryError):
    """``add`` was called with an identifier the repository already holds."""


class AggregateNotFoundError(RepositoryError):
    """``save`` was called with an identifier the repository never held."""


class PersistenceUnavailableError(RepositoryError):
    """The store could not be reached, and retrying did not help.

    The type CLAUDE.md section 4 names by example: "when retries are exhausted, translate to
    port-level error types (e.g. ``PersistenceUnavailableError``)". A deadlock, a dropped
    connection or a statement that overran its timeout is retried three times behind the
    port; what arrives here is the news that trying again did not work.

    Distinct from the two above because it says nothing about the aggregate. A duplicate id
    and a missing one are answers about the data — ask again and they will be the same. This
    one is about the infrastructure, and the same call a minute later may well succeed, which
    is a different thing for a caller to do about it.
    """
