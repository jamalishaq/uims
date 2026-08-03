"""Failures a repository port is allowed to express.

These are the types an adapter translates *into*. Per CLAUDE.md section 4, a raw driver
exception must never cross into the application layer: when the Postgres adapters arrive in
Phase 6, a unique-constraint violation becomes :class:`DuplicateAggregateError` here rather
than surfacing as ``psycopg.IntegrityError``. The application layer is written against this
vocabulary from the start, so that swap changes no calling code.

CLAUDE.md section 4 names this context's sharpest instance of that rule: a unique-constraint
violation on a gateway reference is a *permanent* failure that must never be retried, and it
translates immediately to "the domain's idempotency no-op" — the duplicate is recognised on
the aggregate and the account is left alone. Which is to say the ledger's idempotency
invariant is enforced in the domain, and the database index behind it is a safety net whose
tripping is not an incident.

Absence is deliberately not one of these. ``get`` returns ``None`` for a party nobody has
charged: not finding something you asked about is a normal answer, and here it is the answer
for everybody who has not yet accepted an offer.

A per-context copy of the same three names Academic Records, Admissions, Course Catalog,
Enrollment and the rest each hold. A context may not import another context's code at all,
and the duplication is the price of the boundary.
"""


class RepositoryError(Exception):
    """Base class for every failure a repository port can raise."""


class DuplicateAggregateError(RepositoryError):
    """``add`` was called with an identifier the repository already holds."""


class AggregateNotFoundError(RepositoryError):
    """``save`` was called with an identifier the repository never held."""
