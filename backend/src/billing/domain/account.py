"""The ``Account`` aggregate: one party's money, from the acceptance fee onward.

**One account, one ledger, keyed by a neutral party-id.** CLAUDE.md section 3 is explicit
that Billing holds a "Single ``Account`` aggregate keyed by a neutral party-id: created at
``OfferAccepted`` keyed by applicant_id; linked to the matric number at matriculation. One
continuous ledger from acceptance fee onward." An account per session, or a separate
pre-matriculation ledger handed over to a student account later, would put the university's
answer to "what does this person owe" on a join across records and would give the idempotency
invariant below nowhere to live.

Three invariants hold this together, and each of them is here rather than in a use case
because a rule in an application service is a rule the next caller can skip:

1. **A gateway reference is applied once.** :meth:`apply_payment` recognises a reference it
   already holds and changes nothing — not the payments, not an allocation, not the credit
   balance. Webhook retries are normal traffic (CLAUDE.md section 3), and this is the
   invariant CLAUDE.md section 6 names as escalation-worthy to touch.
2. **Surplus is legal.** Money that no outstanding charge is waiting for becomes a credit
   balance, and the next charge raised absorbs it. "Never assume balance ≤ charges" is a
   sentence about overpayment, which happens: a parent pays a round figure, or two relatives
   both pay.
3. **A charge is raised once per ``(kind, session)``.** Both of this context's event handlers
   consume at-least-once buses, and this is what makes a redelivered ``OfferAccepted`` or
   ``SessionOpened`` a no-op rather than a second bill.

**Allocation is gating-charge-first, then in the order raised.** A payment does not name a
charge — gateways know nothing about this university's fee structure — so the account decides,
and it decides in favour of the charge that is holding something up. The acceptance fee gates
matriculation; the matriculation fee raised in the same breath gates nothing. Paying the
oldest first would leave the ordering between two charges raised in one transaction to be
decided by insertion order, which is not a policy anybody chose.

The aggregate **states facts and does not publish them**: the domain layer may not reach a
port. :meth:`apply_payment` returns ``AcceptanceFeePaid`` inside its outcome and
``RecordPayment`` announces it. Exactly once per party, and structurally rather than by a
flag: settlement is monotonic, a settled charge absorbs nothing further, so the transition
that produces the fact cannot be re-entered.

What is deliberately **not** here is any notion of clearance. There is no percentage, no
"is this student cleared", no threshold. That rule lives entirely behind
``FinancialClearancePort`` (CLAUDE.md section 3) in an adapter Phase 5.2 writes, and a ratio
computed on this aggregate would be the rule leaking out of the one place it is allowed to be.
"""

from collections.abc import Iterable
from datetime import datetime

from billing.domain.charge import Charge, ChargeKind
from billing.domain.errors import InvalidChargeError, PartyAlreadyLinkedError
from billing.domain.events import AcceptanceFeePaid, DomainEvent
from billing.domain.outcomes import (
    ChargeAllocation,
    ChargeAlreadyRaised,
    ChargeOutcome,
    ChargeRaised,
    DuplicatePaymentIgnored,
    PaymentApplied,
    PaymentOutcome,
)
from billing.domain.payment import Payment
from billing.domain.values import Level, Money, require_identifier


class Account:
    """One party's charges, payments and credit balance."""

    def __init__(self, party_id: str, program_id: str, level: Level | None = None) -> None:
        if level is not None and not isinstance(level, Level):
            raise InvalidChargeError("level must be a Level")
        self._party_id = require_identifier(party_id, "party_id")
        self._program_id = require_identifier(program_id, "program_id")
        self._level = level if level is not None else Level()
        self._student_id: str | None = None
        self._charges: list[Charge] = []
        self._payments: list[Payment] = []
        self._credit_balance = Money.zero()

    @classmethod
    def open(cls, party_id: str, program_id: str, *, level: Level | None = None) -> "Account":
        """Open an account for a party who has just accepted an offer.

        The program is the *offered* one, which is not always the one applied for, and the
        level defaults to Billing's own :data:`~billing.domain.values.ENTRY_LEVEL` because no
        event carries one. Both are here rather than looked up: they are what the fee schedule
        is keyed by, and an account that had to ask another context what it costs to run would
        be a batch of a thousand queries every time a session opens.
        """
        return cls(party_id, program_id, level)

    @classmethod
    def restore(
        cls,
        party_id: str,
        program_id: str,
        level: Level,
        *,
        student_id: str | None = None,
        charges: Iterable[Charge] = (),
        payments: Iterable[Payment] = (),
        credit_balance: Money | None = None,
    ) -> "Account":
        """Rebuild a ledger from stored state. A persistence adapter is the only caller.

        **The entries are placed, not replayed.** Re-running ``raise_charge`` and
        ``apply_payment`` would re-run *allocation*, and allocation is where this aggregate's
        decisions live: which charge absorbed which payment, and whether that settlement was
        the one that produced ``AcceptanceFeePaid``. A replay would either publish that fact a
        second time for money banked last year, or — worse — allocate differently from the way
        it was allocated originally, because the gating charge is decided by the order the
        charges were raised in and a replay would be reconstructing that order from the rows it
        is trying to read. The stored ``allocated`` on each charge *is* the record of what was
        decided, and it is restored rather than recomputed.

        ``Charge`` and ``Payment`` are frozen and validate themselves, so each entry is still
        checked. What is not re-checked is the arithmetic between them, and the last argument
        is why it does not need to be: the credit balance is stored, so the identity that money
        in equals money allocated plus credit is carried in the row rather than re-derived from
        it.
        """
        account = cls(party_id, program_id, level)
        if student_id is not None:
            account._student_id = require_identifier(student_id, "student_id")
        for charge in charges:
            if not isinstance(charge, Charge):
                raise InvalidChargeError("a restored account's charges are Charge values")
            account._charges.append(charge)
        for payment in payments:
            if not isinstance(payment, Payment):
                raise InvalidChargeError("a restored account's payments are Payment values")
            account._payments.append(payment)
        if credit_balance is not None:
            if not isinstance(credit_balance, Money):
                raise InvalidChargeError("a restored credit balance must be Money")
            account._credit_balance = credit_balance
        return account

    # ---- identity ----

    @property
    def party_id(self) -> str:
        """The id this account is keyed by: the applicant id it was opened with."""
        return self._party_id

    @property
    def student_id(self) -> str | None:
        """The matric number this party was later issued, or ``None`` until they are one."""
        return self._student_id

    @property
    def party_ids(self) -> frozenset[str]:
        """Every id this account answers to. One before matriculation, two after."""
        return frozenset({self._party_id} | ({self._student_id} if self._student_id else set()))

    @property
    def program_id(self) -> str:
        return self._program_id

    @property
    def level(self) -> Level:
        return self._level

    def link_student_id(self, student_id: str) -> bool:
        """Link the matric number this party was issued. Returns whether anything changed.

        The party-id in CLAUDE.md's glossary made concrete: "applicant_id before matriculation,
        linked to matric number after". One ledger continues; it simply gains a second name.

        Re-linking the same id is a no-op, because whatever eventually drives this will deliver
        at least once. A *different* id is refused: one ledger answering to two people would
        leave no way afterwards to say whose money was whose.
        """
        student_id = require_identifier(student_id, "student_id")
        if self._student_id == student_id:
            return False
        if self._student_id is not None:
            raise PartyAlreadyLinkedError(
                f"account {self._party_id} is already linked to student {self._student_id} "
                f"and cannot also be {student_id}"
            )
        self._student_id = student_id
        return True

    # ---- reading the ledger ----

    @property
    def charges(self) -> tuple[Charge, ...]:
        """Every charge, in the order raised. Frozen values in a tuple: no way in from here."""
        return tuple(self._charges)

    @property
    def payments(self) -> tuple[Payment, ...]:
        """Every payment, in the order received."""
        return tuple(self._payments)

    @property
    def credit_balance(self) -> Money:
        """Money paid that no charge was waiting for. Positive, or zero."""
        return self._credit_balance

    @property
    def total_charged(self) -> Money:
        return self._sum(charge.amount for charge in self._charges)

    @property
    def total_paid(self) -> Money:
        """Everything that ever arrived, whether it was owed or not."""
        return self._sum(payment.amount for payment in self._payments)

    @property
    def total_allocated(self) -> Money:
        """The part of what arrived that a charge absorbed. The rest is the credit balance."""
        return self._sum(charge.allocated for charge in self._charges)

    @property
    def outstanding(self) -> Money:
        """What is still owed across every charge. Never negative — surplus is credit, not debt."""
        return self._sum(charge.outstanding for charge in self._charges)

    @property
    def acceptance_fee_settled(self) -> bool:
        """Whether the gating charge is paid in full. ``False`` while none has been raised."""
        return any(charge.gates_matriculation and charge.is_settled for charge in self._charges)

    def charge_for(self, kind: ChargeKind, session_id: str) -> Charge | None:
        """The charge of one kind for one session, or ``None`` if it was never raised."""
        key = (kind, require_identifier(session_id, "session_id"))
        return next((charge for charge in self._charges if charge.key == key), None)

    def has_charge(self, kind: ChargeKind, session_id: str) -> bool:
        return self.charge_for(kind, session_id) is not None

    def charges_for_session(self, session_id: str) -> tuple[Charge, ...]:
        """Everything charged against one session, in the order raised."""
        session_id = require_identifier(session_id, "session_id")
        return tuple(charge for charge in self._charges if charge.session_id == session_id)

    def payment_for(self, gateway_ref: str) -> Payment | None:
        """The payment made under one gateway reference, or ``None``. The idempotency lookup."""
        gateway_ref = require_identifier(gateway_ref, "gateway_ref")
        return next(
            (payment for payment in self._payments if payment.gateway_ref == gateway_ref), None
        )

    @staticmethod
    def _sum(amounts: Iterable[Money]) -> Money:
        total = Money.zero()
        for amount in amounts:
            total = total + amount
        return total

    # ---- writing ----

    def raise_charge(self, kind: ChargeKind, session_id: str, amount: Money) -> ChargeOutcome:
        """Charge this party ``amount`` for ``kind`` in ``session_id``.

        Idempotent on ``(kind, session_id)``: a charge already raised is returned as
        :class:`~billing.domain.outcomes.ChargeAlreadyRaised` and *nothing* changes, including
        when the amount offered differs. A schedule republished at a new figure does not
        retroactively re-price a bill somebody has already been sent and may already have
        paid; that is an administrative act, and there is no use case for it yet.

        Any standing credit is poured into the new charge straight away, which is what makes
        an overpayment at acceptance time turn into a part-paid session fee later rather than
        a balance somebody has to remember to spend.
        """
        session_id = require_identifier(session_id, "session_id")
        existing = self.charge_for(kind, session_id)
        if existing is not None:
            return ChargeAlreadyRaised(charge=existing)

        position = len(self._charges)
        self._charges.append(Charge(kind=kind, session_id=session_id, amount=amount))
        allocations, events = self._absorb_credit()
        return ChargeRaised(
            charge=self._charges[position],
            settled_from_credit=self._sum(
                allocation.amount
                for allocation in allocations
                if (allocation.kind, allocation.session_id) == (kind, session_id)
            ),
            events=events,
        )

    def raise_acceptance_fee(self, session_id: str, amount: Money) -> ChargeOutcome:
        """The gating charge. Settling it publishes ``AcceptanceFeePaid``."""
        return self.raise_charge(ChargeKind.ACCEPTANCE, session_id, amount)

    def raise_matriculation_fee(self, session_id: str, amount: Money) -> ChargeOutcome:
        """Raised beside the acceptance fee, and gating nothing (CLAUDE.md section 4)."""
        return self.raise_charge(ChargeKind.MATRICULATION, session_id, amount)

    def raise_session_fee(self, session_id: str, amount: Money) -> ChargeOutcome:
        """What a session costs this party. Applied in a batch when the session opens."""
        return self.raise_charge(ChargeKind.SESSION, session_id, amount)

    def apply_payment(
        self, *, gateway_ref: str, amount: Money, received_at: datetime
    ) -> PaymentOutcome:
        """Record money the gateway confirmed, and allocate it.

        **The idempotency invariant.** A ``gateway_ref`` already on this ledger returns
        :class:`~billing.domain.outcomes.DuplicatePaymentIgnored` and the account is untouched
        — the check comes before the payment is even constructed, so a replay carrying a
        malformed amount is ignored rather than rejected. Silent, in the sense CLAUDE.md means:
        not an error, not a refusal, and not something a retrying webhook can turn into an
        incident.

        The amount recorded is the one that arrived. This method has no idea what any intent
        was for, and Phase 5.3 must keep it that way: "the ledger records the amount the
        gateway confirms, never the intent's amount".

        Anything no charge was waiting for becomes credit. The returned ``events`` carry
        ``AcceptanceFeePaid`` exactly when this payment is the one that settled the gating
        charge — not before, and not on the payments that follow it.
        """
        gateway_ref = require_identifier(gateway_ref, "gateway_ref")
        already_held = self.payment_for(gateway_ref)
        if already_held is not None:
            return DuplicatePaymentIgnored(gateway_ref=gateway_ref, original=already_held)

        payment = Payment(gateway_ref=gateway_ref, amount=amount, received_at=received_at)
        allocations, remaining, events = self._allocate(payment.amount)
        self._payments.append(payment)
        self._credit_balance = self._credit_balance + remaining
        return PaymentApplied(
            payment=payment,
            allocations=allocations,
            credited=remaining,
            credit_balance=self._credit_balance,
            events=events,
        )

    # ---- allocation ----

    def _allocation_order(self) -> list[int]:
        """Which charges get paid first: gating ones, then in the order they were raised.

        Positions rather than charges, because absorbing replaces the frozen value at its
        position. ``sorted`` is stable, so charges that agree on gating keep the order they
        were raised in — the acceptance and matriculation fees of one offer among them.
        """
        outstanding = [index for index, charge in enumerate(self._charges) if not charge.is_settled]
        return sorted(outstanding, key=lambda index: not self._charges[index].gates_matriculation)

    def _allocate(
        self, available: Money
    ) -> tuple[tuple[ChargeAllocation, ...], Money, tuple[DomainEvent, ...]]:
        """Pour ``available`` into the outstanding charges, and report what is left over."""
        allocations: list[ChargeAllocation] = []
        events: list[DomainEvent] = []
        remaining = available

        for index in self._allocation_order():
            if remaining.is_zero:
                break
            charge = self._charges[index]
            absorbed, taken = charge.absorb(remaining)
            if taken.is_zero:
                continue
            self._charges[index] = absorbed
            remaining = remaining - taken
            allocations.append(
                ChargeAllocation(kind=charge.kind, session_id=charge.session_id, amount=taken)
            )
            if absorbed.is_settled and absorbed.gates_matriculation:
                events.append(AcceptanceFeePaid(applicant_id=self._party_id))

        return tuple(allocations), remaining, tuple(events)

    def _absorb_credit(self) -> tuple[tuple[ChargeAllocation, ...], tuple[DomainEvent, ...]]:
        """Spend the standing credit balance on whatever is now outstanding."""
        if self._credit_balance.is_zero:
            return (), ()
        allocations, remaining, events = self._allocate(self._credit_balance)
        self._credit_balance = remaining
        return allocations, events

    def __repr__(self) -> str:
        return (
            f"Account(party_id={self._party_id!r}, program_id={self._program_id!r}, "
            f"level={self._level}, charges={len(self._charges)}, "
            f"payments={len(self._payments)}, outstanding={self.outstanding}, "
            f"credit={self._credit_balance})"
        )
