"""Inbound adapter: an academic session has opened, so its fees are due.

Faculty & Department owns the academic calendar and announces when a session opens; its
``EventPublisherPort`` names this context as the audience — "Billing to ``SessionOpened``" —
without knowing anything about what happens next. What happens next is that every active
account gets charged what the schedule says its program and level costs.

Unlike ``OfferAccepted``, this event has a real publisher today, so this handler has both
halves: a typed message and the :meth:`from_payload` that builds one from what crossed the
bus. What crosses is a name and a mapping of primitives; this is the deserialising half of
what ``faculty_department.domain.events`` promises when it says "an outbound adapter
serialises them at the boundary".

**``academic_year`` is read and discarded.** It arrives — the event carries it, and it comes
through as a nested mapping because it is a value object over there — and this context has no
use for it: fees are keyed by session, program and level, and a year is Faculty &
Department's way of naming the session rather than a thing to bill against. Taking it would
mean holding a piece of another context's domain in order to ignore it.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from billing.application.apply_session_fees import ApplySessionFees, SessionFeesApplied

SESSION_OPENED = "SessionOpened"
"""The name this context subscribes under. A string, because the bus carries no classes."""


@dataclass(frozen=True)
class SessionOpenedMessage:
    """What this context takes from Faculty & Department's ``SessionOpened``.

    One field of the two the event carries. The session id is the key a fee schedule is
    published under and a charge is raised against; nothing else about the calendar reaches
    this context, and nothing else needs to.
    """

    session_id: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "SessionOpenedMessage":
        """Build the message from what the bus delivered.

        The field is read by name and the rest of the payload is ignored, so a publisher
        adding a field does not break this consumer. A *missing* ``session_id`` is a
        ``KeyError`` and stays one: it means the contract this context was written against is
        not what arrived, and a session quietly defaulted into shape would bill a whole
        cohort against the wrong year.
        """
        return cls(session_id=str(payload["session_id"]))


class SessionOpenedHandler:
    """Applies a session's fee schedule when the session opens."""

    def __init__(self, apply_session_fees: ApplySessionFees) -> None:
        self._apply_session_fees = apply_session_fees

    async def handle(self, message: SessionOpenedMessage) -> SessionFeesApplied:
        """Charge every active account this session's fee.

        Redelivery is normal: a replayed ``SessionOpened`` re-runs the batch, and every
        account already charged answers ``ChargeAlreadyRaised``. Nobody is billed twice, and
        the summary tells the two apart.
        """
        return await self._apply_session_fees.execute(message.session_id)

    async def on_message(self, payload: Mapping[str, object]) -> None:
        """Subscribe *this* to a bus: deserialise, then handle.

        The signature a transport can call without knowing anything about this context —
        which is what lets the wiring that connects Faculty & Department to Billing be a
        single line in a composition root, importing neither context's event type.
        """
        await self.handle(SessionOpenedMessage.from_payload(payload))
