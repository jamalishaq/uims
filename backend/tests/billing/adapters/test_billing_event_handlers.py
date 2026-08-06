"""The two inbound handlers: translation, and nothing else.

What is worth proving about a handler is not that it works but that it is *not a second way
of doing the thing*. Both of these call the same use case an administrator would, so neither
can drift into charging a different amount or skipping a check the other applies.

Both now have a real publisher, so both carry a ``from_payload`` and can be subscribed to a
bus. ``OfferAccepted`` waited five phases for its half: Admissions published nothing, and a
deserialiser written ahead of a publisher is a guess at payload keys that fails at the one
moment it matters. The keys asserted below are the ones Admissions actually emits.
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

    async def test_an_accepted_offer_opens_a_ledger_with_both_charges(
        self,
        offer_accepted_handler: OfferAcceptedHandler,
        accounts: AccountRepositoryPort,
        published_schedule: FeeSchedule,
    ) -> None:
        await offer_accepted_handler.handle(an_offer())

        stored = await accounts.get(APPLICANT_ID)
        assert stored is not None
        assert [charge.kind for charge in stored.charges] == [
            ChargeKind.ACCEPTANCE,
            ChargeKind.MATRICULATION,
        ]

    async def test_a_message_with_no_level_uses_billing_s_entry_level(
        self,
        offer_accepted_handler: OfferAcceptedHandler,
        accounts: AccountRepositoryPort,
        published_schedule: FeeSchedule,
    ) -> None:
        """Admissions has no opinion about a level, and the adapter does not invent one."""
        await offer_accepted_handler.handle(an_offer())
        stored = await accounts.get(APPLICANT_ID)
        assert stored is not None
        assert stored.level == Level(100)

    async def test_redelivery_opens_no_second_account(
        self,
        offer_accepted_handler: OfferAcceptedHandler,
        accounts: AccountRepositoryPort,
        published_schedule: FeeSchedule,
    ) -> None:
        first = await offer_accepted_handler.handle(an_offer())
        second = await offer_accepted_handler.handle(an_offer())

        stored = await accounts.get(APPLICANT_ID)
        assert stored is not None
        assert (first.was_already_open, second.was_already_open) == (False, True)
        assert len(stored.charges) == 2

    def test_reads_the_offer_off_the_payload(self) -> None:
        """The deserialiser arrived with the publisher, rather than guessing ahead of it."""
        message = OfferAcceptedMessage.from_payload(
            {
                "applicant_id": APPLICANT_ID,
                "program_id": CSC_PROGRAM_ID,
                "session_id": SESSION_2026,
            }
        )
        assert message == an_offer()

    def test_a_payload_with_no_level_uses_billing_s_entry_level(self) -> None:
        """Admissions has no opinion about a level, so no key for one is on the wire."""
        message = OfferAcceptedMessage.from_payload(
            {
                "applicant_id": APPLICANT_ID,
                "program_id": CSC_PROGRAM_ID,
                "session_id": SESSION_2026,
            }
        )
        assert message.level == 100

    def test_ignores_fields_a_publisher_adds_later(self) -> None:
        message = OfferAcceptedMessage.from_payload(
            {
                "applicant_id": APPLICANT_ID,
                "program_id": CSC_PROGRAM_ID,
                "session_id": SESSION_2026,
                "applied_program_id": "prog-someone-else",
                "decided_at": "2026-08-01",
            }
        )
        assert message == an_offer()

    @pytest.mark.parametrize("missing", ["applicant_id", "program_id", "session_id"])
    def test_a_missing_field_raises_rather_than_defaulting(self, missing: str) -> None:
        """A ledger opened against a defaulted applicant or program is worse than a delivery
        that failed loudly."""
        payload = {
            "applicant_id": APPLICANT_ID,
            "program_id": CSC_PROGRAM_ID,
            "session_id": SESSION_2026,
        }
        del payload[missing]
        with pytest.raises(KeyError):
            OfferAcceptedMessage.from_payload(payload)

    async def test_on_message_deserialises_then_handles(
        self,
        offer_accepted_handler: OfferAcceptedHandler,
        accounts: AccountRepositoryPort,
        published_schedule: FeeSchedule,
    ) -> None:
        """The signature a bus calls, which is what lets the wiring be one line in the root."""
        await offer_accepted_handler.on_message(
            {
                "applicant_id": APPLICANT_ID,
                "program_id": CSC_PROGRAM_ID,
                "session_id": SESSION_2026,
            }
        )
        stored = await accounts.get(APPLICANT_ID)
        assert stored is not None
        assert len(stored.charges) == 2


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

    async def test_charges_every_priced_account_when_the_session_opens(
        self,
        session_opened_handler: SessionOpenedHandler,
        accounts: AccountRepositoryPort,
        published_schedule: FeeSchedule,
    ) -> None:
        await accounts.add(Account.open(APPLICANT_ID, CSC_PROGRAM_ID))

        result = await session_opened_handler.handle(SessionOpenedMessage(session_id=SESSION_2026))

        stored = await accounts.get(APPLICANT_ID)
        assert stored is not None
        assert result.charged == (APPLICANT_ID,)
        assert stored.charge_for(ChargeKind.SESSION, SESSION_2026) is not None

    async def test_a_redelivered_session_charges_nobody_twice(
        self,
        session_opened_handler: SessionOpenedHandler,
        accounts: AccountRepositoryPort,
        published_schedule: FeeSchedule,
    ) -> None:
        await accounts.add(Account.open(APPLICANT_ID, CSC_PROGRAM_ID))
        payload = {"session_id": SESSION_2026, "academic_year": {"value": 2026}}

        await session_opened_handler.on_message(payload)
        await session_opened_handler.on_message(payload)

        stored = await accounts.get(APPLICANT_ID)
        assert stored is not None
        assert len(stored.charges_for_session(SESSION_2026)) == 1
