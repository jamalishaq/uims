"""Outbound port for storing and retrieving payment intents."""

from abc import ABC, abstractmethod

from billing.domain.payment_intent import PaymentIntent


class PaymentIntentRepositoryPort(ABC):
    """Persistence for the ``PaymentIntent`` aggregate, keyed by the gateway's reference.

    Keyed by the reference and not by a party, because a party has many intents over the years
    and every question anybody asks of this repository starts from a reference: a webhook
    quotes one, a sweep verifies one. That the key is the gateway's own string rather than one
    this system minted is what lets a confirmation arriving from outside find its intent
    without a lookup table, and it is the same key the resulting ``Payment`` carries on the
    ledger.

    There is no ``remove``, for the reason ``AccountRepositoryPort`` gives: an intent is part
    of the record of what the university asked for and what came back, and a written-off
    checkout is exactly the row somebody will want to see when a payer insists they paid.

    **Notice what is not in these signatures: a ``datetime``.** There is no
    ``stale_before(as_of)``, and its absence is not an oversight — every type crossing a
    Billing port must be one this context defines or a builtin, which
    ``tests/billing/test_port_types_are_billing_owned.py`` enforces. The TTL is applied by
    ``ReconcilePaymentIntents`` against the instant it was handed, which is where it belongs
    anyway: when a checkout has gone quiet enough to chase is policy, and pushing it into a
    ``WHERE`` clause would put a piece of this context's judgement in the one layer that is
    meant to be swappable.
    """

    @abstractmethod
    def add(self, intent: PaymentIntent) -> None:
        """Store an intent under a reference nothing has used yet.

        Raises:
            DuplicateAggregateError: an intent is already held for that reference. A gateway
                reference identifies one movement of money, so a second intent claiming the
                same one is a caller's mistake and not a retry to absorb.
        """

    @abstractmethod
    def save(self, intent: PaymentIntent) -> None:
        """Persist a transition on an intent that is already stored.

        Raises:
            AggregateNotFoundError: no intent was ever added under that reference.
        """

    @abstractmethod
    def get(self, reference: str) -> PaymentIntent | None:
        """Return the intent opened under ``reference``, or ``None`` if there is none.

        ``None`` is an answer rather than a failure everywhere else in this system; here it is
        the one place that is worth a second look. A *signed* webhook quoting a reference this
        university never issued is not routine, and the use case refuses it rather than
        inventing an intent to hang it on.
        """

    @abstractmethod
    def all_initiated(self) -> tuple[PaymentIntent, ...]:
        """Every intent the gateway has said nothing about yet, in the order opened.

        Not "every stale intent": staleness is a judgement about a TTL and an instant, and
        neither is something a repository has. This narrows the sweep to the only intents that
        could possibly need chasing — a confirmed, failed or abandoned one has already been
        answered — and the caller decides which of them have gone quiet long enough to ask
        about.
        """
