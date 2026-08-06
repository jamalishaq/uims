"""Which status each of this context's refusals leaves as.

``AuthenticationFailedError`` is a **401**, and it is the only entry here that is not about the
shape of a request. Everything else in this table follows the pattern the other seven contexts
use; this one says "we do not know who you are", which is the one answer a client responds to
by going somewhere else entirely.

``LoginIdAlreadyIssuedError`` and ``PrincipalAlreadyHasCredentialError`` are **409s** rather
than 422s. The request was well-formed and describes a credential that would be perfectly valid
— it collides with one that already exists, which is what a 409 means and what a 422 does not.
"""

from http_api import ExceptionStatuses
from identity.application.errors import (
    ApplicationError,
    AuthenticationFailedError,
    CredentialNotFoundError,
    LoginIdAlreadyIssuedError,
    PrincipalAlreadyHasCredentialError,
)
from identity.domain.errors import IdentityError
from identity.ports.errors import (
    AggregateNotFoundError,
    DuplicateAggregateError,
    PersistenceUnavailableError,
    RepositoryError,
    TokenIssuanceError,
)

EXCEPTION_STATUSES: ExceptionStatuses = {
    # 401 — we do not know who you are. One entry, one message, three causes: see
    # ``application/errors.py`` on why an unknown login id and a wrong password are the same
    # answer.
    AuthenticationFailedError: 401,
    # 404 — no such credential. Only reachable behind a university-scoped token, which is why
    # it may say so where the login flow may not.
    CredentialNotFoundError: 404,
    AggregateNotFoundError: 404,
    # 409 — a well-formed request for a credential that would collide with one held.
    LoginIdAlreadyIssuedError: 409,
    PrincipalAlreadyHasCredentialError: 409,
    DuplicateAggregateError: 409,
    # 422 — the request cannot describe a credential this context will store.
    IdentityError: 422,
    ApplicationError: 422,
    # 5xx — the store, and the signing key.
    PersistenceUnavailableError: 503,
    TokenIssuanceError: 500,
    RepositoryError: 500,
}
