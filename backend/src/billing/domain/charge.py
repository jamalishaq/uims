"""What the university has asked one party to pay, and how much of it has been met.

Three kinds, and the difference between them is not the amount but what settling one *does*.
The acceptance fee gates matriculation — Admissions will not matriculate an applicant until
``AcceptanceFeePaid`` has arrived — and the matriculation fee, despite its name, gates
nothing at all. CLAUDE.md section 4 says so twice, once as a rule and once in the list of
things not to do: "Do not gate matriculation on the matriculation fee." That distinction is
:attr:`ChargeKind.gates_matriculation`, and it is the only place in the system with an
opinion about it.

A charge is **frozen**, and the account replaces it when it absorbs money rather than editing
it in place. The same arrangement Academic Records uses for a transcript line: a ledger entry
that a caller could reach in and adjust is a ledger entry whose history means nothing. The
only way a charge changes is :meth:`Charge.absorb`, which hands back a *new* charge and says
how much it took.

Charges are keyed by ``(kind, session_id)`` and that key is what makes both of this context's
event handlers safe to redeliver: raising a charge that is already on the account changes
nothing. An acceptance fee belongs to the session the offer was made in, and a session fee to
the session it pays for, so the pair is unique by construction rather than by convention.
"""

from dataclasses import dataclass, field
from enum import Enum

from billing.domain.errors import InvalidChargeError
from billing.domain.values import Money, require_identifier


class ChargeKind(Enum):
    """What a charge is for. Its value is the wording a bursary statement would use."""

    ACCEPTANCE = "acceptance fee"
    MATRICULATION = "matriculation fee"
    SESSION = "session fee"

    @property
    def gates_matriculation(self) -> bool:
        """Whether settling this charge unlocks a state transition somewhere else.

        True for exactly one kind. The matriculation fee is an outstanding balance and
        nothing more (CLAUDE.md section 3), and the session fee gates registration rather
        than matriculation — through ``FinancialClearancePort``, on a rule that lives in an
        adapter and not here.
        """
        return self is ChargeKind.ACCEPTANCE

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Charge:
    """One demand for payment, and how much of it has been met so far."""

    kind: ChargeKind
    session_id: str
    amount: Money
    allocated: Money = field(default_factory=Money.zero)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ChargeKind):
            raise InvalidChargeError("charge kind must be a ChargeKind")
        object.__setattr__(self, "session_id", require_identifier(self.session_id, "session_id"))
        if not isinstance(self.amount, Money) or not isinstance(self.allocated, Money):
            raise InvalidChargeError("charge amounts must be Money")
        if self.amount.is_zero:
            raise InvalidChargeError(
                f"a {self.kind} for {self.session_id} would be for nothing; a charge of zero "
                "is a charge nobody raised"
            )
        if self.allocated > self.amount:
            raise InvalidChargeError(
                f"{self.allocated} has been allocated to a {self.kind} of {self.amount}; "
                "a charge cannot absorb more than it is owed"
            )

    @property
    def key(self) -> tuple[ChargeKind, str]:
        """What makes this charge the one it is. Raising the same key twice is a no-op."""
        return (self.kind, self.session_id)

    @property
    def outstanding(self) -> Money:
        """What is still owed on this charge. Zero once it is settled."""
        return self.amount - self.allocated

    @property
    def is_settled(self) -> bool:
        return self.outstanding.is_zero

    @property
    def gates_matriculation(self) -> bool:
        return self.kind.gates_matriculation

    def absorb(self, available: Money) -> tuple["Charge", Money]:
        """Take what this charge is owed out of ``available``.

        Returns the charge as it now stands and the amount actually taken — which is the
        smaller of what is available and what is outstanding, so a payment larger than the
        debt leaves the remainder for the next charge or, if there is none, for the credit
        balance. A settled charge takes nothing and hands itself back unchanged.
        """
        if not isinstance(available, Money):
            raise InvalidChargeError("available must be Money")
        taken = min(available, self.outstanding)
        if taken.is_zero:
            return self, taken
        return (
            Charge(
                kind=self.kind,
                session_id=self.session_id,
                amount=self.amount,
                allocated=self.allocated + taken,
            ),
            taken,
        )

    def __str__(self) -> str:
        return f"{self.kind} {self.session_id}: {self.allocated} of {self.amount}"
