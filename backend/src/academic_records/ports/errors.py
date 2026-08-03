"""Failures a repository port is allowed to express.

These are the types an adapter translates *into*. Per CLAUDE.md section 4, a raw driver
exception must never cross into the application layer: when the Postgres adapters arrive
in Phase 6, a unique-constraint violation becomes :class:`DuplicateAggregateError` here
rather than surfacing as ``psycopg.IntegrityError``. The application layer is written
against this vocabulary from the start, so that swap changes no calling code.

Absence is deliberately *not* one of these. ``get`` returns ``None`` for a student nobody
has graded yet: not finding something you asked about is a normal answer, and here it is
the *usual* one — every student's first submitted grade arrives at a repository holding
nothing for them.

A per-context copy of the same three names Admissions, Course Catalog, Enrollment and the
rest each hold. A context may not import another context's code at all, and the
duplication is the price of the boundary.
"""


class RepositoryError(Exception):
    """Base class for every failure a repository port can raise."""


class DuplicateAggregateError(RepositoryError):
    """``add`` was called with an identifier the repository already holds."""


class AggregateNotFoundError(RepositoryError):
    """``save`` was called with an identifier the repository never held."""
