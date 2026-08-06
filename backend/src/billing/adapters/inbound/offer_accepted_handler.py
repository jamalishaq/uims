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

**The ``from_payload`` half arrived with the publisher, which is how it was always meant to.**
For five phases this file had only a typed message: Admissions published nothing, so writing a
deserialiser would have meant guessing the payload's keys, and a guess that is wrong fails at
the one moment it matters. Admissions now has an ``EventPublisherPort`` and an ``AcceptOffer``
use case behind it, so the keys below are read off a real contract rather than invented.
"""

from collections.abc import Mapping
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

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "OfferAcceptedMessage":
        """Build the message from what the bus delivered.

        Three fields read by name; the rest of the payload is ignored, so a publisher adding
        one does not break this consumer. ``level`` is deliberately not read at all — no key
        for it exists on the wire, because Admissions has no opinion about a level and this
        context's ``ENTRY_LEVEL`` is the answer.

        A missing key is a ``KeyError`` and stays one: it means the contract this context was
        written against is not what arrived, and an applicant or program quietly defaulted
        into shape would open a ledger against the wrong person or price it for the wrong
        program.
        """
        return cls(
            applicant_id=str(payload["applicant_id"]),
            program_id=str(payload["program_id"]),
            session_id=str(payload["session_id"]),
        )


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

    async def on_message(self, payload: Mapping[str, object]) -> None:
        """Subscribe *this* to a bus: deserialise, then handle.

        The signature a transport can call without knowing anything about this context —
        which is what lets the wiring that connects Admissions to Billing be a single line in
        a composition root, importing neither context's event type.
        """
        await self.handle(OfferAcceptedMessage.from_payload(payload))
