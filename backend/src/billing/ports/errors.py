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
