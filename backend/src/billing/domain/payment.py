"""One confirmed movement of money into an account.

Three fields, exactly as CLAUDE.md section 3 specifies: ``(gateway_ref, amount, timestamp)``.
What is missing from that list is the point of the design. A payment does not name a charge.
Gateways do not know that this university distinguishes an acceptance fee from a session fee,
and a ledger entry that carried a charge reference would mean the gateway had been told —
which is exactly what "keep ``RecordPayment`` and the Account gateway-agnostic" forbids.
Where the money goes is the account's decision, made at allocation time.

``gateway_ref`` is **the idempotency key**, and the reason this entity is worth having at all.
Webhook retries are normal (CLAUDE.md section 3), so the same reference will arrive more than
once and the second arrival must change nothing. That invariant is enforced on the aggregate,
where an invariant belongs, but it is *expressible* only because every payment carries the
reference the gateway used rather than an id this system minted.

The amount is the one the gateway confirmed. Nothing here has any notion of what an intent
was for: "intent confirmed" never implies "charge settled", and Phase 5.3's ``PaymentIntent``
will hand this ledger the amount that actually moved, not the amount that was asked for.
"""

from dataclasses import dataclass
from datetime import datetime

from billing.domain.errors import InvalidPaymentError
from billing.domain.values import Money, require_identifier, require_timestamp


@dataclass(frozen=True)
class Payment:
    """Money that arrived, as the gateway reported it. Frozen: a received payment is history."""

    gateway_ref: str
    amount: Money
    received_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "gateway_ref", require_identifier(self.gateway_ref, "gateway_ref"))
        if not isinstance(self.amount, Money):
            raise InvalidPaymentError("payment amount must be Money")
        if self.amount.is_zero:
            raise InvalidPaymentError(
                f"payment {self.gateway_ref} is for nothing; a zero payment moves no money "
                "and would still consume its gateway reference"
            )
        object.__setattr__(self, "received_at", require_timestamp(self.received_at, "received_at"))

    def __str__(self) -> str:
        return f"{self.gateway_ref}: {self.amount} at {self.received_at.isoformat()}"
