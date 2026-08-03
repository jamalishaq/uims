"""What the account answers when the answer is legitimately "nothing happened".

These are *outcomes*, not events. Nothing publishes them and no other context will ever see
one: they are what :meth:`Account.apply_payment` and :meth:`Account.raise_charge` hand back to
the caller that asked. The shape — a frozen dataclass plus a union alias — is borrowed from a
domain event because the shape is a good one, in the manner of Enrollment's ``SeatOutcome``.

They exist because of the sharpest word in CLAUDE.md's Billing section: a duplicate
``gateway_ref`` is a *silent* no-op. Silent means it is not an error, not a log line somebody
has to triage, and not something a webhook retry can turn into an incident. It does not mean
invisible. A no-op the caller could not distinguish from a first delivery would be untestable
— "same gateway_ref applied twice changes the ledger once" is exactly the claim these types
let a test make — and it would leave a use case unable to decide whether the aggregate is
worth saving.

:class:`PaymentApplied` carries the events the allocation produced rather than publishing
them. The domain layer may not reach a port (the dependency rule), so the aggregate states
the fact and the use case announces it.
"""

from dataclasses import dataclass

from billing.domain.charge import Charge, ChargeKind
from billing.domain.events import DomainEvent
from billing.domain.payment import Payment
from billing.domain.values import Money


@dataclass(frozen=True)
class ChargeAllocation:
    """How much of one payment went to one charge.

    The charge is named by its key rather than carried whole, because by the time a caller
    reads this the charge has been replaced by the one that absorbed the money, and holding
    the superseded copy would invite somebody to read a stale ``outstanding`` off it.
    """

    kind: ChargeKind
    session_id: str
    amount: Money

    def __str__(self) -> str:
        return f"{self.amount} to {self.kind} {self.session_id}"


@dataclass(frozen=True)
class PaymentApplied:
    """The payment was new: it is on the ledger and has been allocated."""

    payment: Payment
    allocations: tuple[ChargeAllocation, ...]
    credited: Money
    """The part of this payment that no charge was waiting for. Surplus is legal."""
    credit_balance: Money
    """The account's standing credit *after* this payment, not just this payment's part."""
    events: tuple[DomainEvent, ...]
    """Facts the allocation produced. Empty unless a gating charge settled on this payment."""


@dataclass(frozen=True)
class DuplicatePaymentIgnored:
    """The gateway reference was already on the ledger. Nothing changed at all.

    ``original`` is the payment already held, so a caller can see that the amounts agree —
    or, more interestingly, that they do not. A gateway replaying a reference with a
    different amount is still ignored here, because the reference is the identity of the
    movement of money; noticing the discrepancy is reconciliation's job in Phase 5.3.
    """

    gateway_ref: str
    original: Payment

    @property
    def events(self) -> tuple[DomainEvent, ...]:
        """Nothing happened, so there is nothing to announce.

        A property rather than a field, so it cannot be constructed as anything else, and
        present at all so that a caller can publish ``outcome.events`` without first asking
        which outcome it is holding. A use case that had to branch before publishing is a use
        case that will one day branch wrongly.
        """
        return ()


PaymentOutcome = PaymentApplied | DuplicatePaymentIgnored
"""Everything :meth:`Account.apply_payment` can answer. Callers must handle both."""


@dataclass(frozen=True)
class ChargeRaised:
    """The charge is new and now stands against the account."""

    charge: Charge
    settled_from_credit: Money
    """What a standing credit balance immediately absorbed. Usually zero."""
    events: tuple[DomainEvent, ...]


@dataclass(frozen=True)
class ChargeAlreadyRaised:
    """A charge with this kind and session was already on the account. Nothing changed.

    The ordinary answer to a redelivered ``OfferAccepted`` or ``SessionOpened``, and the
    reason neither handler needs a de-duplication table of its own.
    """

    charge: Charge

    @property
    def events(self) -> tuple[DomainEvent, ...]:
        """Nothing happened, so nothing to announce. See :class:`DuplicatePaymentIgnored`."""
        return ()


ChargeOutcome = ChargeRaised | ChargeAlreadyRaised
"""Everything :meth:`Account.raise_charge` can answer. Callers must handle both."""
