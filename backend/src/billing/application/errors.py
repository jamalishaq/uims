"""Failures a use case can raise that the domain has no opinion about.

The split is the one every other context here draws. A domain error means the ledger was
asked to do something it cannot do — a negative amount, a second student id on one account.
These mean the *orchestration* could not proceed: something the use case had to load was not
there.

Nothing here is about a payment being wrong. A duplicate gateway reference and an overpayment
are both normal, both handled on the aggregate, and neither is an exception — they come back
as outcomes (:mod:`billing.domain.outcomes`). A ledger whose ordinary traffic ran through
error handlers would have somebody investigating webhook retries at three in the morning.
"""


class BillingApplicationError(Exception):
    """Base class for every failure this layer raises on its own account."""


class AccountNotFoundError(BillingApplicationError):
    """No account is stored for that party.

    Raised by the use cases that operate on an existing ledger — recording a payment, linking
    a matric number, reading a statement. Never by opening an account, which creates one when
    it finds none.

    For :class:`~billing.application.record_payment.RecordPayment` this is the important
    refusal: money has arrived for somebody Billing has never heard of. Opening an account to
    receive it would invent a party out of a gateway reference, so the payment is refused and
    the mismatch stays visible for a human to reconcile.
    """


class PaymentIntentNotFoundError(BillingApplicationError):
    """No payment intent is stored under that gateway reference.

    The refusal that matters on the webhook path, and it is deliberately not survivable. A
    request whose signature verified came from the gateway, which proves who sent it and
    nothing about whose money it is; the party a confirmation lands on is read off the intent,
    because it was this system that opened the checkout and this system that knows who for.

    So a reference with no intent behind it has nowhere to go. Recording it against a party
    named in the payload would let a compromised gateway account, or a replay of a request
    signed for a different institution, credit whichever ledger the body asked for. The
    mismatch is left visible for a human, exactly as :class:`AccountNotFoundError` leaves
    money for an unknown party visible rather than making it fit.
    """


class FeeScheduleNotPublishedError(BillingApplicationError):
    """No fee schedule has been published for that session.

    Both callers refuse rather than carry on, and each for its own reason. An offer accepted
    against an unpriced session would open an account with no acceptance charge on it —
    leaving matriculation gated on a charge that does not exist, which is worse than a failed
    handler. A session opened before its fees are set would charge nobody at all and look
    exactly like a session where everybody happened to be unpriced.
    """
