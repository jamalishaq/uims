"""Which status each of this context's refusals leaves as.

Three entries here are decisions rather than lookups.

``WebhookSignatureError`` is a **401 carrying nothing**. The exception itself is built to be
uninformative — "Carries no detail about what was expected. A caller who can tell 'wrong length'
from 'wrong bytes' from 'wrong encoding' has been handed a way to search for the answer" — and
the route preserves that by never adding any. The status says the request was not from the
gateway and stops there.

``MalformedWebhookError`` is a **400 and a different thing entirely**: the signature was valid,
so this is the gateway itself sending something unreadable. Its docstring calls that "an
integration bug worth an alert rather than a background rate of noise", and splitting the two
statuses is what lets a monitor tell them apart.

``PaymentIntentFinalError`` is a **409 that arrives after a successful write**. When a gateway
contradicts itself the money is banked *and then* the contradiction is raised — CLAUDE.md
section 3, confirmed. A client seeing this 409 must not read it as "nothing happened": the
ledger has the payment. It is a flag for a person, not a failed request to retry.
"""

from billing.adapters.inbound.payment_webhook import (
    MalformedWebhookError,
    PaymentWebhookError,
    WebhookSignatureError,
)
from billing.application.errors import (
    AccountNotFoundError,
    BillingApplicationError,
    FeeScheduleNotPublishedError,
    PaymentIntentNotFoundError,
)
from billing.domain.errors import (
    BillingError,
    PartyAlreadyLinkedError,
    PaymentIntentFinalError,
)
from billing.ports.errors import (
    AggregateNotFoundError,
    DuplicateAggregateError,
    PersistenceUnavailableError,
    RepositoryError,
)
from billing.ports.payment_gateway import PaymentGatewayError, PaymentGatewayUnavailableError
from http_api import ExceptionStatuses

EXCEPTION_STATUSES: ExceptionStatuses = {
    # 401 — not from the gateway. Deliberately says nothing else.
    WebhookSignatureError: 401,
    # 400 — signed by the gateway, and unreadable.
    MalformedWebhookError: 400,
    PaymentWebhookError: 400,
    # 404 — no such ledger, checkout or schedule.
    AccountNotFoundError: 404,
    PaymentIntentNotFoundError: 404,
    FeeScheduleNotPublishedError: 404,
    AggregateNotFoundError: 404,
    # 409 — contradicts what is already true. See the note on PaymentIntentFinalError.
    PaymentIntentFinalError: 409,
    PartyAlreadyLinkedError: 409,
    DuplicateAggregateError: 409,
    # 422 — the request cannot describe money moving.
    BillingError: 422,
    BillingApplicationError: 422,
    # 5xx — the store, or the third party.
    PersistenceUnavailableError: 503,
    PaymentGatewayUnavailableError: 503,
    PaymentGatewayError: 502,
    RepositoryError: 500,
}
