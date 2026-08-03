"""Value objects and the shared construction guards used across this context.

The guards live here so that "an entity must never be constructible into an invalid state"
is enforced in one place rather than restated in every constructor. They duplicate the
guards in Academic Records, Admissions, Course Catalog, Enrollment, Faculty & Department and
Student Profile by design, not by oversight: a context may not import another context's
domain models (CLAUDE.md section 4), and the architecture fitness test enforces it.

:class:`Money` is the one that earns its keep here more than anywhere else in the system.
Every other context can get away with plain numbers; a ledger cannot. Three properties are
worth stating outright, because each of them is a bug this class exists to make
unrepresentable:

* **Never ``float``.** ``0.1 + 0.2`` is not ``0.3`` in binary floating point, and a
  university that reconciles its bursary against a payment gateway would find the difference.
  ``Decimal`` throughout, and a ``float`` handed to the constructor is refused rather than
  converted — by the time it arrives the precision is already gone.
* **Never negative.** A credit balance is a positive figure held on the account, not a
  negative charge. Money that could go below zero would let a refund be modelled by accident,
  and refunds are a deferred admin use case (CLAUDE.md section 3) rather than a subtraction
  nobody meant.
* **Never rounded silently.** Two decimal places is kobo, the smallest unit anybody can
  actually pay; a third is a data-entry error or a currency this system does not handle, and
  it is refused rather than quietly rounded into something that no longer adds up.

:class:`Level` is Billing's own, and the entry level below it is Billing's default. The same
arrangement Student Profile arrived at for ``StudentMatriculated``: an event that has no
opinion about a level should not force its consumer to invent one at the boundary.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from billing.domain.errors import (
    InvalidAmountError,
    InvalidLevelError,
    InvalidPaymentError,
    MissingIdentifierError,
)

MINOR_UNIT_PLACES = 2
"""Decimal places a payable amount may carry. Kobo: the smallest unit anybody can transfer."""

LEVEL_STEP = 100
"""Levels run 100, 200, 300 — the same step Student Profile uses, and ours to change."""

ENTRY_LEVEL = 100
"""The level Billing books a freshly admitted account at.

``OfferAccepted`` carries no level, and neither does anything else that reaches this context.
Rather than leave the fee schedule unable to price a new account, Billing states its own
default here — exactly as Student Profile's ``DEFAULT_ENTRY_LEVEL`` does for the same missing
field on ``StudentMatriculated``. It is a default and a construction argument, never a rule:
how many levels a LASU program runs to, and when a student moves between them, is an
institutional fact (CLAUDE.md section 6). Nothing in this phase advances a level, and that
absence is visible rather than papered over with a guess.
"""

DEFAULT_INTENT_TTL = timedelta(hours=1)
"""How long a payment intent may sit unanswered before reconciliation sweeps it.

Billing's own default and a construction argument, in the manner of :data:`ENTRY_LEVEL` above
— an operational figure this context is entitled to choose, rather than an institutional fact
it would have to be told (CLAUDE.md section 6). It is longer than any checkout a payer will
sit through, so a sweep will not race somebody still typing their card details, and short
enough that a webhook lost at nine in the morning is caught the same working day rather than
leaving a paid-up student unable to register.

It is a *presumption of death*, not a deadline: nothing expires money. An expired intent is
only a candidate for the question "did this actually go through", and the answer comes from
the gateway rather than from the clock — which is why
:meth:`~billing.domain.payment_intent.PaymentIntent.abandon` will not act without it.
"""


def require_identifier(value: str, field: str) -> str:
    """Return ``value`` stripped, rejecting anything blank.

    Identifiers minted by other contexts — an applicant id, a program id, a session id, a
    matric number — are opaque to us: non-emptiness is the only thing we can honestly check.
    A gateway reference is opaque for a stronger reason still: its shape is the gateway's,
    and a ledger that parsed one would break the day a second gateway is added.
    """
    if not isinstance(value, str) or not value.strip():
        raise MissingIdentifierError(f"{field} must be a non-empty identifier")
    return value.strip()


def require_text(value: str, field: str) -> str:
    """Return ``value`` stripped, rejecting anything blank."""
    if not isinstance(value, str) or not value.strip():
        raise MissingIdentifierError(f"{field} must be non-empty")
    return value.strip()


def require_timestamp(value: datetime, field: str = "timestamp") -> datetime:
    """Return ``value``, rejecting anything that is not a ``datetime``.

    Whether it carries a timezone is not checked here, and deliberately: what a gateway sends
    is the gateway's business, and an adapter that normalises it is the place to say so. What
    a ledger entry may not be is undated.
    """
    if not isinstance(value, datetime):
        raise InvalidPaymentError(f"{field} must be a datetime")
    return value


@dataclass(frozen=True, order=True)
class Money:
    """An amount in naira, to kobo, never negative.

    Ordered and hashable, so amounts can be compared and summed without anybody writing out
    the comparison again. Accepts ``Decimal``, ``int`` or ``str`` — and refuses ``float``,
    because a float has already lost the precision this class exists to keep.
    """

    amount: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", self._coerce(self.amount))

    @staticmethod
    def _coerce(value: object) -> Decimal:
        if isinstance(value, bool | float):
            raise InvalidAmountError(
                f"amount must be a Decimal, int or str, got {type(value).__name__}; "
                "a float cannot represent money exactly"
            )
        if not isinstance(value, Decimal | int | str):
            raise InvalidAmountError(f"amount must be a Decimal, int or str, got {value!r}")
        try:
            amount = Decimal(value)
        except (ArithmeticError, InvalidOperation, ValueError) as malformed:
            raise InvalidAmountError(f"amount {value!r} is not a number") from malformed
        if not amount.is_finite():
            raise InvalidAmountError(f"amount {value!r} is not a finite number")
        if amount < 0:
            raise InvalidAmountError(f"amount {amount} is negative; money here is never below zero")
        if -amount.as_tuple().exponent > MINOR_UNIT_PLACES:  # type: ignore[operator]
            raise InvalidAmountError(
                f"amount {amount} carries more than {MINOR_UNIT_PLACES} decimal places; "
                "kobo is the smallest unit that can be paid"
            )
        return amount.quantize(Decimal(1).scaleb(-MINOR_UNIT_PLACES))

    @classmethod
    def zero(cls) -> "Money":
        """Nothing. What an unpaid charge has absorbed and what an empty ledger holds."""
        return cls(Decimal(0))

    @property
    def is_zero(self) -> bool:
        return self.amount == 0

    def __add__(self, other: "Money") -> "Money":
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.amount + other.amount)

    def __sub__(self, other: "Money") -> "Money":
        """Subtract, refusing to go below zero.

        A subtraction that would be negative is a caller having got its arithmetic wrong —
        allocating more to a charge than the charge is owed, say — and returning a negative
        amount would hide it in a total somewhere downstream.
        """
        if not isinstance(other, Money):
            return NotImplemented
        if other.amount > self.amount:
            raise InvalidAmountError(
                f"cannot subtract {other} from {self}: money here is never below zero"
            )
        return Money(self.amount - other.amount)

    def __str__(self) -> str:
        return f"{self.amount:.2f}"

    def __repr__(self) -> str:
        return f"Money('{self.amount:.2f}')"


@dataclass(frozen=True, order=True)
class Level:
    """An academic level: 100, 200, and so on.

    A positive multiple of 100 is the whole rule, and there is deliberately no ceiling — how
    many levels a program runs to is an institutional fact (CLAUDE.md section 6), and a
    maximum guessed here would start refusing to price real students the first time a program
    ran longer than the guess. Billing's own copy of Student Profile's value object: the two
    say the same thing today and are free to disagree tomorrow.
    """

    value: int = ENTRY_LEVEL

    def __post_init__(self) -> None:
        if not isinstance(self.value, int) or isinstance(self.value, bool):
            raise InvalidLevelError("level must be an integer")
        if self.value < LEVEL_STEP or self.value % LEVEL_STEP:
            raise InvalidLevelError(
                f"level {self.value} must be a positive multiple of {LEVEL_STEP}"
            )

    def __str__(self) -> str:
        return str(self.value)
