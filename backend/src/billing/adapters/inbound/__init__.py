"""Billing inbound adapters.

Two handlers, and between them they are every way a charge gets raised in this system: an
applicant accepts an offer, and a session opens. Money moving the other way — payments —
arrives through ``RecordPayment``, and the adapter that will call it is Phase 5.3's webhook.

There is no webhook here yet, and its absence is the plan rather than a gap. CLAUDE.md
section 3 requires that adapter to verify the gateway's signature "before the payload reaches
any use case", and section 4 forbids generating or refactoring that code without explicit
human review of the diff. It arrives on its own, in its own change.

Neither handler decides anything. Admissions has already established that the offer was
acceptable and Faculty & Department that the session may open; these files translate a message
into a command and let the domain on this side rule on the rest.
"""

from billing.adapters.inbound.offer_accepted_handler import (
    OFFER_ACCEPTED,
    OfferAcceptedHandler,
    OfferAcceptedMessage,
)
from billing.adapters.inbound.session_opened_handler import (
    SESSION_OPENED,
    SessionOpenedHandler,
    SessionOpenedMessage,
)

__all__ = [
    "OFFER_ACCEPTED",
    "SESSION_OPENED",
    "OfferAcceptedHandler",
    "OfferAcceptedMessage",
    "SessionOpenedHandler",
    "SessionOpenedMessage",
]
