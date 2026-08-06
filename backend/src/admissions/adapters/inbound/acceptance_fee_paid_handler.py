"""Inbound adapter: the acceptance fee cleared, so matriculation is unlocked.

The only thing this context consumes. Billing's ``EventPublisherPort`` states that an
acceptance fee was paid without knowing what anybody does about it — its docstring is
explicit that "Billing does not know matriculation exists" — and this is the file on the
other side that does know.

It *translates*, it does not decide. Whether the payment was real, which charge it settled,
and whether that charge was the gating one were all determined in Billing before the event
was published, and none of it is re-checked here. What clearing the fee *means* — that a
person may now matriculate this applicant — belongs to the domain on this side.

:class:`AcceptanceFeePaidMessage` is **this context's own reading of the event**, not
Billing's class. A consumer never imports a publisher's event type (CLAUDE.md section 3),
and the architecture fitness test would reject the import anyway.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from admissions.application.record_acceptance_fee_paid import (
    AcceptanceFeeRecorded,
    RecordAcceptanceFeePaid,
    RecordAcceptanceFeePaidCommand,
)

ACCEPTANCE_FEE_PAID = "AcceptanceFeePaid"
"""The name this context subscribes under. A string, because the bus carries no classes."""


@dataclass(frozen=True)
class AcceptanceFeePaidMessage:
    """What this context takes from Billing's ``AcceptanceFeePaid``.

    The one field the event carries, and it is deliberately an applicant id rather than a
    party id: Billing keys its ledger on a neutral identifier that becomes a matric number
    later, but the fact it announces here is about somebody who has not matriculated, so the
    two agree for exactly as long as this event is meaningful.

    No amount. What was paid, against which charge, and what remains outstanding are Billing's
    to know; all that crosses is that the gate is open.
    """

    applicant_id: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "AcceptanceFeePaidMessage":
        """Build the message from what the bus delivered.

        The field is read by name and the rest of the payload ignored, so a publisher adding
        a field does not break this consumer. A *missing* ``applicant_id`` is a ``KeyError``
        and stays one: it means the contract this context was written against is not what
        arrived, and an applicant quietly defaulted into shape would unlock matriculation for
        the wrong person.
        """
        return cls(applicant_id=str(payload["applicant_id"]))


class AcceptanceFeePaidHandler:
    """Unlocks matriculation when the gating fee clears."""

    def __init__(self, record_acceptance_fee_paid: RecordAcceptanceFeePaid) -> None:
        self._record_acceptance_fee_paid = record_acceptance_fee_paid

    async def handle(self, message: AcceptanceFeePaidMessage) -> AcceptanceFeeRecorded:
        """Set the fee-cleared flag on the applicant.

        Redelivery is normal, not exceptional: a bus that guarantees at-least-once delivery
        will replay this event, including after a registrar has already matriculated the
        applicant. The idempotency lives on the aggregate, where it is an invariant rather
        than a handler's good manners, and the result says ``was_already_cleared`` so a
        caller can tell the two apart.
        """
        return await self._record_acceptance_fee_paid.execute(
            RecordAcceptanceFeePaidCommand(applicant_id=message.applicant_id)
        )

    async def on_message(self, payload: Mapping[str, object]) -> None:
        """Subscribe *this* to a bus: deserialise, then handle.

        The signature a transport can call without knowing anything about this context —
        which is what lets the wiring that connects Billing to Admissions be a single line in
        a composition root, importing neither context's event type.
        """
        await self.handle(AcceptanceFeePaidMessage.from_payload(payload))
