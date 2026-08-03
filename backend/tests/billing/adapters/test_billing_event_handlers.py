"""The two inbound handlers: translation, and nothing else.

What is worth proving about a handler is not that it works but that it is *not a second way
of doing the thing*. Both of these call the same use case an administrator would, so neither
can drift into charging a different amount or skipping a check the other applies.

The asymmetry between them is deliberate and documented in the adapters themselves:
``SessionOpened`` has a real publisher today, so its handler has a ``from_payload`` and can be
subscribed to a bus; ``OfferAccepted`` has none, so its handler stops at the typed message
rather than guessing at payload keys.
"""

import pytest

from billing.adapters.inbound import (
    OFFER_ACCEPTED,
    SESSION_OPENED,
    OfferAcceptedHandler,
    OfferAcceptedMessage,
    SessionOpenedHandler,
    SessionOpenedMessage,
)
from billing.domain import Account, ChargeKind, FeeSchedule, Level
from billing.ports import AccountRepositoryPort

APPLICANT_ID = "app-0001"
CSC_PROGRAM_ID = "prog-csc-bsc"
SESSION_2026 = "sess-2026"


def an_offer(**overrides: object) -> OfferAcceptedMessage:
    fields: dict[str, object] = {
        "applicant_id": APPLICANT_ID,
        "program_id": CSC_PROGRAM_ID,
        "session_id": SESSION_2026,
    }
    fields.update(overrides)
    return OfferAcceptedMessage(**fields)  # type: ignore[arg-type]


class TestOfferAccepted:
    def test_subscribes_under_the_publisher_s_own_event_name(self) -> None:
        assert OFFER_ACCEPTED == "OfferAccepted"

    def test_an_accepted_offer_opens_a_ledger_with_both_charges(
        self,
        offer_accepted_handler: OfferAcceptedHandler,
        accounts: AccountRepositoryPort,
        published_schedule: FeeSchedule,
    ) -> None:
        offer_accepted_handler.handle(an_offer())

        stored = accounts.get(APPLICANT_ID)
        assert stored is not None
        assert [charge.kind for charge in stored.charges] == [
            ChargeKind.ACCEPTANCE,
            ChargeKind.MATRICULATION,
        ]

    def test_a_message_with_no_level_uses_billing_s_entry_level(
        self,
        offer_accepted_handler: OfferAcceptedHandler,
        accounts: AccountRepositoryPort,
        published_schedule: FeeSchedule,
    ) -> None:
        """Admissions has no opinion about a level, and the adapter does not invent one."""
        offer_accepted_handler.handle(an_offer())
        stored = accounts.get(APPLICANT_ID)
        assert stored is not None
        assert stored.level == Level(100)

    def test_redelivery_opens_no_second_account(
        self,
        offer_accepted_handler: OfferAcceptedHandler,
        accounts: AccountRepositoryPort,
        published_schedule: FeeSchedule,
    ) -> None:
        first = offer_accepted_handler.handle(an_offer())
        second = offer_accepted_handler.handle(an_offer())

        stored = accounts.get(APPLICANT_ID)
        assert stored is not None
        assert (first.was_already_open, second.was_already_open) == (False, True)
        assert len(stored.charges) == 2

    def test_has_no_deserialiser_until_admissions_publishes(self) -> None:
        """Writing one now would mean guessing the payload's keys — a guess that is wrong fails
        at the one moment it matters. Student Profile made the same call for
        ``StudentMatriculated``."""
        assert not hasattr(OfferAcceptedMessage, "from_payload")
        assert not hasattr(OfferAcceptedHandler, "on_message")


class TestSessionOpened:
    def test_subscribes_under_the_publisher_s_own_event_name(self) -> None:
        assert SESSION_OPENED == "SessionOpened"

    def test_reads_the_session_off_the_payload(self) -> None:
        message = SessionOpenedMessage.from_payload(
            {"session_id": SESSION_2026, "academic_year": {"value": 2026}}
        )
        assert message == SessionOpenedMessage(session_id=SESSION_2026)

    def test_ignores_the_academic_year_the_event_carries(self) -> None:
        """It is a Faculty & Department value object arriving as a nested mapping; taking it
        would mean holding a piece of another context's domain in order to ignore it."""
        assert not hasattr(SessionOpenedMessage(session_id=SESSION_2026), "academic_year")

    def test_ignores_fields_a_publisher_adds_later(self) -> None:
        message = SessionOpenedMessage.from_payload(
            {"session_id": SESSION_2026, "opened_by": "registrar", "starts_on": "2026-09-01"}
        )
        assert message.session_id == SESSION_2026

    def test_a_payload_missing_the_session_is_a_key_error(self) -> None:
        """A session quietly defaulted into shape would bill a cohort against the wrong year."""
        with pytest.raises(KeyError):
            SessionOpenedMessage.from_payload({"academic_year": {"value": 2026}})

    def test_charges_every_priced_account_when_the_session_opens(
        self,
        session_opened_handler: SessionOpenedHandler,
        accounts: AccountRepositoryPort,
        published_schedule: FeeSchedule,
    ) -> None:
        accounts.add(Account.open(APPLICANT_ID, CSC_PROGRAM_ID))

        result = session_opened_handler.handle(SessionOpenedMessage(session_id=SESSION_2026))

        stored = accounts.get(APPLICANT_ID)
        assert stored is not None
        assert result.charged == (APPLICANT_ID,)
        assert stored.charge_for(ChargeKind.SESSION, SESSION_2026) is not None

    def test_a_redelivered_session_charges_nobody_twice(
        self,
        session_opened_handler: SessionOpenedHandler,
        accounts: AccountRepositoryPort,
        published_schedule: FeeSchedule,
    ) -> None:
        accounts.add(Account.open(APPLICANT_ID, CSC_PROGRAM_ID))
        payload = {"session_id": SESSION_2026, "academic_year": {"value": 2026}}

        session_opened_handler.on_message(payload)
        session_opened_handler.on_message(payload)

        stored = accounts.get(APPLICANT_ID)
        assert stored is not None
        assert len(stored.charges_for_session(SESSION_2026)) == 1
