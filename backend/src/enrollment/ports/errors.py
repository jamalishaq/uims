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
