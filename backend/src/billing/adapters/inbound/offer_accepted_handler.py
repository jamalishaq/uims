"""Inbound adapter: an applicant took up their offer, so a ledger exists.

The moment Billing begins. CLAUDE.md section 3: the account is "created at ``OfferAccepted``
keyed by applicant_id", and on that event both admission charges are raised — the gating
acceptance fee and the non-gating matriculation fee.

It *translates*, it does not decide. Whether the applicant held an offer, whether the offer
was still open, whether the program was theirs to accept — all settled in Admissions before
the event was published, and none of it re-checked here. What the fees are and how they behave
belongs to the domain on this side. This file turns a message into a command.

:class:`OfferAcceptedMessage` is **this context's own reading of the event**, not Admissions'
class. A consumer never imports a publisher's event type (CLAUDE.md section 3), and the
architecture fitness test would reject the import anyway.

**There is no ``from_payload`` here yet, deliberately.** Admissions publishes nothing today —
its ports package says so outright: the event publisher is "Not here yet, and deliberately",
and ``OfferAccepted`` "is not raised by anything built so far". Writing a deserialiser now
would mean guessing the payload's keys, and a guess that is wrong fails at the one moment it
matters. Student Profile made the same call for ``StudentMatriculated``: the typed half is
written, and the wire half arrives with the publisher. The handler is exercised by calling
:meth:`OfferAcceptedHandler.handle` with a message, which is what a bus adapter will do once
there is one.
"""

from dataclasses import dataclass

from billing.application.open_account_for_offer import (
    AccountOpened,
    OpenAccountForOffer,
    OpenAccountForOfferCommand,
)
from billing.domain.values import ENTRY_LEVEL

OFFER_ACCEPTED = "OfferAccepted"
"""The name this context will subscribe under. A string, because the bus carries no classes."""


@dataclass(frozen=True)
class OfferAcceptedMessage:
    """What this context takes from Admissions' ``OfferAccepted``.

    The three fields CLAUDE.md says the event carries. ``program_id`` is the *offered*
    program, which is not always the one applied for — an applicant placed on an alternative
    is billed for where they are going.

    ``level`` defaults rather than being required: Admissions has no opinion about a level,
    and a bus adapter with nothing to fill it with should not have to invent one. Billing's
    own :data:`~billing.domain.values.ENTRY_LEVEL` is the default, and it is what the fee
    schedule will be keyed by when the session opens.
    """

    applicant_id: str
    program_id: str
    session_id: str
    level: int = ENTRY_LEVEL


class OfferAcceptedHandler:
    """Opens the ledger an accepted offer creates."""

    def __init__(self, open_account_for_offer: OpenAccountForOffer) -> None:
        self._open_account_for_offer = open_account_for_offer

    async def handle(self, message: OfferAcceptedMessage) -> AccountOpened:
        """Open the account and raise both admission charges.

        Redelivery is normal, not exceptional: a bus that guarantees at-least-once delivery
        will replay this event, and a second acceptance fee charged to somebody who has
        already paid theirs is the failure that would cause. The idempotency lives on the
        aggregate, where it is an invariant rather than a handler's good manners, and the
        result says ``was_already_open`` so a caller can tell.
        """
        return await self._open_account_for_offer.execute(
            OpenAccountForOfferCommand(
                applicant_id=message.applicant_id,
                program_id=message.program_id,
                session_id=message.session_id,
                level=message.level,
            )
        )
