"""Billing inbound adapters.

Two event handlers, and between them they are every way a charge gets raised in this system:
an applicant accepts an offer, and a session opens. Money moving the other way arrives through
the third adapter here — the gateway webhook — which is the only thing in this system that
ever calls ``ConfirmPayment``, and through it ``RecordPayment``.

**The webhook is not like the other two, and the difference is worth stating.** The event
handlers consume an internal bus: whatever is on it was put there by another context of this
same system, so the question they answer is only "what does this mean to Billing". The webhook
faces the public internet, where the first question is whether the message is from the gateway
at all. CLAUDE.md section 3 requires it to verify the signature "before the payload reaches any
use case" and section 4 flags the path as one not to generate or refactor without human review
of the diff — which is why the verification lives in an object of its own, in a file that does
nothing else, rather than as a step inside a handler.

None of the three decides anything about money. Admissions has already established that the
offer was acceptable, Faculty & Department that the session may open, and the gateway that the
funds moved; these files translate a message into a command and let the domain on this side
rule on the rest.
"""

from billing.adapters.inbound.offer_accepted_handler import (
    OFFER_ACCEPTED,
    OfferAcceptedHandler,
    OfferAcceptedMessage,
)
from billing.adapters.inbound.payment_webhook import (
    PAYSTACK_SIGNATURE_HEADER,
    MalformedWebhookError,
    PaymentWebhookError,
    PaymentWebhookHandler,
    PaymentWebhookMessage,
    WebhookSignatureError,
    WebhookSignatureVerifier,
)
from billing.adapters.inbound.session_opened_handler import (
    SESSION_OPENED,
    SessionOpenedHandler,
    SessionOpenedMessage,
)

__all__ = [
    "OFFER_ACCEPTED",
    "PAYSTACK_SIGNATURE_HEADER",
    "SESSION_OPENED",
    "MalformedWebhookError",
    "OfferAcceptedHandler",
    "OfferAcceptedMessage",
    "PaymentWebhookError",
    "PaymentWebhookHandler",
    "PaymentWebhookMessage",
    "SessionOpenedHandler",
    "SessionOpenedMessage",
    "WebhookSignatureError",
    "WebhookSignatureVerifier",
]
