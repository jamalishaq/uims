"""The in-memory ``PaymentIntentRepositoryPort``, against its port's contract."""

from datetime import datetime

import pytest

from billing.adapters.outbound import InMemoryPaymentIntentRepository
from billing.domain import GatewayStatus, GatewayVerification, Money, PaymentIntent
from billing.ports import AggregateNotFoundError, DuplicateAggregateError

JULY = datetime(2026, 7, 1, 9, 30)
AUGUST = datetime(2026, 8, 1, 9, 30)


def an_intent(reference: str = "psk-ref-0001", party_id: str = "app-0001") -> PaymentIntent:
    return PaymentIntent.initiate(
        reference=reference, party_id=party_id, amount=Money("20000"), initiated_at=JULY
    )


@pytest.fixture
def repository() -> InMemoryPaymentIntentRepository:
    return InMemoryPaymentIntentRepository()


def test_an_added_intent_can_be_read_back(repository: InMemoryPaymentIntentRepository) -> None:
    intent = an_intent()
    repository.add(intent)

    assert repository.get("psk-ref-0001") is intent


def test_a_reference_nobody_opened_is_none_rather_than_a_failure(
    repository: InMemoryPaymentIntentRepository,
) -> None:
    assert repository.get("psk-ref-nobody") is None


def test_a_reference_cannot_be_claimed_twice(
    repository: InMemoryPaymentIntentRepository,
) -> None:
    repository.add(an_intent())

    with pytest.raises(DuplicateAggregateError):
        repository.add(an_intent())


def test_saving_an_intent_that_was_never_added_is_refused(
    repository: InMemoryPaymentIntentRepository,
) -> None:
    with pytest.raises(AggregateNotFoundError):
        repository.save(an_intent())


class TestAllInitiated:
    def test_it_returns_open_intents_in_the_order_opened(
        self, repository: InMemoryPaymentIntentRepository
    ) -> None:
        first, second = an_intent("psk-ref-0001"), an_intent("psk-ref-0002")
        repository.add(first)
        repository.add(second)

        assert repository.all_initiated() == (first, second)

    @pytest.mark.parametrize("resolve", ["confirm", "fail", "abandon"])
    def test_an_answered_intent_drops_out(
        self, repository: InMemoryPaymentIntentRepository, resolve: str
    ) -> None:
        """A confirmed, failed or abandoned intent has been answered. Nothing to chase."""
        intent = an_intent()
        repository.add(intent)

        if resolve == "confirm":
            intent.confirm(amount=Money("20000"), at=AUGUST)
        elif resolve == "fail":
            intent.fail("declined", at=AUGUST)
        else:
            intent.abandon(
                verified=GatewayVerification(
                    reference="psk-ref-0001", status=GatewayStatus.UNKNOWN
                ),
                at=AUGUST,
            )
        repository.save(intent)

        assert repository.all_initiated() == ()

    def test_an_empty_repository_answers_with_nothing(
        self, repository: InMemoryPaymentIntentRepository
    ) -> None:
        assert repository.all_initiated() == ()
