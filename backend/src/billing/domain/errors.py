"""Failures this context's domain layer is allowed to express.

Every one of them ends in ``Error`` and descends from :class:`BillingError`, so a caller can
catch "the ledger refused" without naming each refusal (CLAUDE.md section 2).

What is *not* here is worth as much as what is. A duplicate ``gateway_ref`` raises nothing:
it is the idempotency invariant doing its job, and a webhook retry is normal traffic rather
than a fault (CLAUDE.md section 3). A payment larger than everything owed raises nothing
either — the ledger allows surplus, and a credit balance is a state the university's bursary
recognises, not an error. Both are *outcomes*, and they live in
:mod:`billing.domain.outcomes`.

A per-context copy of the guard vocabulary Admissions, Enrollment and the rest each hold. A
context may not import another context's domain models (CLAUDE.md section 4), and the
architecture fitness test enforces it.
"""


class BillingError(Exception):
    """Base class for every refusal this context's domain layer makes."""


class MissingIdentifierError(BillingError):
    """An identifier — a party, a program, a session, a gateway reference — was blank."""


class InvalidAmountError(BillingError):
    """An amount of money was negative, not a number, or carried more than kobo precision."""


class InvalidLevelError(BillingError):
    """A level was not a positive multiple of 100."""


class InvalidChargeError(BillingError):
    """A charge was asked for in a shape it cannot take — a zero amount, or an unknown kind."""


class InvalidFeeScheduleError(BillingError):
    """A fee schedule was published with a duplicated or malformed line."""


class InvalidPaymentError(BillingError):
    """A payment was offered without a gateway reference, an amount, or a timestamp."""


class PartyAlreadyLinkedError(BillingError):
    """An account already linked to one student id was offered a different one.

    Re-linking the *same* id is a no-op, because at-least-once delivery is normal. Linking a
    second, different id would mean one ledger answering to two people, and there would be no
    way afterwards to say whose money was whose.
    """


class InvalidPaymentIntentError(BillingError):
    """A payment intent was offered a reference, an amount, a TTL or evidence it cannot take."""


class PaymentIntentFinalError(BillingError):
    """An intent that has reached a terminal state was asked to move again.

    Terminal means confirmed or failed, and not abandoned: an abandonment is a presumption the
    TTL made, and a later confirmation is a fact the gateway stated, so money that turns out to
    have moved can still be recorded against the intent it was for.

    A *replayed* confirmation raises nothing — it is the ordinary answer to a retrying webhook
    and comes back as :class:`~billing.domain.payment_intent.PaymentIntentAlreadyResolved`.
    What this refuses is a genuine contradiction, of which there is one: a gateway that
    reported a reference failed and then reports the same reference succeeded. Nothing in this
    context can decide which of the two the gateway meant.
    """
