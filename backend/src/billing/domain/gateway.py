"""What a payment gateway says when this context asks it about a reference.

Billing's own reading of an external system's answer, and the reason it is in ``domain/``
rather than beside the port: ``PaymentGatewayPort`` is typed in these terms, and every type
crossing a Billing port has to be one this context defines
(``tests/billing/test_port_types_are_billing_owned.py``). A fact object defined in ``ports/``
could not be read by the domain layer, which may not import outward — and
:meth:`PaymentIntent.abandon` reads one. The same arrangement Enrollment arrived at for
``CourseFacts`` and ``AcademicStanding``.

**Four statuses, and the fourth is the one that matters.** A gateway asked about a reference
can say the money arrived, that the attempt failed, that it is still working on it — or it
can fail to recognise the reference at all. Collapsing that last case into "failed" would be
this context inventing a fact: a reference the gateway has never heard of is *not* evidence
that a payment failed, it is evidence that no payment was ever attempted, and the two lead to
different states. ``UNKNOWN`` is also where a gateway that answers in a vocabulary this
translation does not cover has to land, because an adapter that guessed would be guessing
about money.

The amount is here because a verification is the *other* way the ledger learns what was
confirmed, and CLAUDE.md section 3 is unambiguous that what gets recorded is "the amount the
gateway confirms, never the intent's amount" — a reconciliation that healed a lost webhook by
recording what was asked for rather than what was taken would defeat the whole exercise. Both
it and ``paid_at`` are optional, because only a successful verification has either.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from billing.domain.errors import InvalidPaymentIntentError
from billing.domain.values import Money, require_identifier, require_timestamp


class GatewayStatus(Enum):
    """What the gateway reports about one reference. Its value is the wording it means."""

    SUCCESS = "success"
    """The money moved. A verification carrying this must carry an amount."""

    FAILED = "failed"
    """The attempt was made and did not succeed. The gateway is sure."""

    PENDING = "pending"
    """Still in flight. Not an answer yet, and specifically not a licence to abandon."""

    UNKNOWN = "unknown"
    """The gateway does not recognise the reference, or answered in terms we do not read."""

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class GatewayVerification:
    """The gateway's answer about one reference, translated into this context's terms.

    Frozen, and carried around rather than re-fetched: it is evidence, and evidence that could
    be edited between being obtained and being acted on would not be worth demanding.
    :meth:`PaymentIntent.abandon` requires one, which is how "verify before abandoning"
    (CLAUDE.md section 3) becomes an invariant rather than a step somebody remembers.
    """

    reference: str
    status: GatewayStatus
    amount: Money | None = None
    paid_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "reference", require_identifier(self.reference, "reference"))
        if not isinstance(self.status, GatewayStatus):
            raise InvalidPaymentIntentError("status must be a GatewayStatus")
        if self.amount is not None and not isinstance(self.amount, Money):
            raise InvalidPaymentIntentError("verified amount must be Money")
        if self.paid_at is not None:
            require_timestamp(self.paid_at, "paid_at")
        if self.status is GatewayStatus.SUCCESS and self.amount is None:
            raise InvalidPaymentIntentError(
                f"the gateway reported {self.reference} as successful without an amount; "
                "the ledger records what the gateway confirms, so there is nothing to record"
            )

    @property
    def succeeded(self) -> bool:
        return self.status is GatewayStatus.SUCCESS

    @property
    def is_conclusive(self) -> bool:
        """Whether this answer settles the question. ``PENDING`` does not.

        A gateway still working on a reference has told us nothing we can act on, and the one
        action reconciliation would otherwise take — writing the intent off — is exactly the
        one that races a payment about to complete.
        """
        return self.status is not GatewayStatus.PENDING

    def __str__(self) -> str:
        return f"{self.reference}: {self.status}" + (f" of {self.amount}" if self.amount else "")
