"""The quota invariant: a cycle gives away exactly as many places as it has, and no more.

The boundary is the whole file. An off-by-one here is not a bug that shows up as a wrong
number on a report — it is a person who was told they had a place at a university that had
already given it away, so the last place and the one after it are asserted separately
rather than sampled.

The other half is what a full cycle *does*. ``QuotaExhausted`` is a value that gets
returned, not an exception that gets raised (CLAUDE.md section 3), because a full program
is the expected end of a popular program's cycle and the alternative-offer flow reads it
as a normal answer. That is asserted directly, so a later refactor cannot quietly turn it
into an error class and still pass.

Zero infrastructure: one aggregate, no repository, no ports.
"""

import pytest

from admissions.domain import (
    AdmissionCycle,
    AdmissionsError,
    InvalidOffersMadeError,
    InvalidQuotaError,
    MissingIdentifierError,
    OfferRecorded,
    QuotaExhausted,
)

PROGRAM_ID = "prg-csc"
SESSION_ID = "sess-2026"


def a_cycle(quota: int = 3, **overrides: object) -> AdmissionCycle:
    fields: dict[str, object] = {
        "program_id": PROGRAM_ID,
        "session_id": SESSION_ID,
        "quota": quota,
    }
    fields.update(overrides)
    return AdmissionCycle(**fields)  # type: ignore[arg-type]


def a_full_cycle(quota: int = 3) -> AdmissionCycle:
    cycle = a_cycle(quota)
    for _ in range(quota):
        cycle.offer()
    return cycle


class TestOpeningACycle:
    def test_a_new_cycle_has_given_away_nothing(self) -> None:
        cycle = AdmissionCycle.open(PROGRAM_ID, SESSION_ID, 250)

        assert cycle.program_id == PROGRAM_ID
        assert cycle.session_id == SESSION_ID
        assert cycle.quota == 250
        assert cycle.offers_made == 0
        assert cycle.places_remaining == 250
        assert cycle.is_full is False

    def test_a_cycle_can_resume_from_the_offers_it_has_already_made(self) -> None:
        """Storage hands back a cycle mid-intake; it must not forget what it gave away."""
        cycle = a_cycle(quota=100, offers_made=40)

        assert cycle.offers_made == 40
        assert cycle.places_remaining == 60

    @pytest.mark.parametrize("field", ["program_id", "session_id"])
    @pytest.mark.parametrize("blank", ["", "   "])
    def test_a_blank_identifier_is_rejected(self, field: str, blank: str) -> None:
        with pytest.raises(MissingIdentifierError):
            a_cycle(**{field: blank})

    @pytest.mark.parametrize("quota", [-1, -250])
    def test_a_negative_quota_is_rejected(self, quota: int) -> None:
        with pytest.raises(InvalidQuotaError):
            a_cycle(quota)

    @pytest.mark.parametrize("quota", ["250", 250.0, None, True])
    def test_a_quota_that_is_not_a_whole_number_is_rejected(self, quota: object) -> None:
        """``True`` is an int to Python and a data-entry accident to an admissions office."""
        with pytest.raises(InvalidQuotaError):
            a_cycle(quota)  # type: ignore[arg-type]

    def test_a_cycle_cannot_start_already_over_its_own_quota(self) -> None:
        """An invariant that could be bypassed at construction is not an invariant."""
        with pytest.raises(InvalidOffersMadeError):
            a_cycle(quota=10, offers_made=11)

    def test_a_cycle_cannot_start_with_a_negative_number_of_offers(self) -> None:
        with pytest.raises(InvalidOffersMadeError):
            a_cycle(quota=10, offers_made=-1)

    def test_a_cycle_may_start_exactly_at_its_quota(self) -> None:
        """The boundary is legal at construction too: a full cycle is a real thing to load."""
        cycle = a_cycle(quota=10, offers_made=10)

        assert cycle.is_full is True
        assert cycle.places_remaining == 0


class TestTheQuotaBoundary:
    @pytest.mark.parametrize("quota", [1, 2, 5, 250])
    def test_every_place_up_to_the_quota_is_given_away(self, quota: int) -> None:
        cycle = a_cycle(quota)

        for place in range(1, quota + 1):
            outcome = cycle.offer()

            assert outcome == OfferRecorded(PROGRAM_ID, SESSION_ID, place, quota)
            assert cycle.offers_made == place
            assert cycle.places_remaining == quota - place

    @pytest.mark.parametrize("quota", [1, 2, 5, 250])
    def test_the_offer_after_the_last_place_is_quota_exhausted(self, quota: int) -> None:
        cycle = a_full_cycle(quota)

        outcome = cycle.offer()

        assert outcome == QuotaExhausted(PROGRAM_ID, SESSION_ID, quota)
        assert cycle.offers_made == quota

    def test_the_place_before_the_last_one_still_succeeds(self) -> None:
        """The named boundary, stated on its own: quota-1 is a place, quota is not."""
        cycle = a_cycle(quota=3)
        cycle.offer()

        second_to_last = cycle.offer()
        last = cycle.offer()
        past_the_end = cycle.offer()

        assert isinstance(second_to_last, OfferRecorded)
        assert isinstance(last, OfferRecorded)
        assert isinstance(past_the_end, QuotaExhausted)

    def test_a_cycle_admitting_nobody_is_full_before_anyone_applies(self) -> None:
        """A program not admitting this session is a real cycle, not a missing one."""
        cycle = AdmissionCycle.open(PROGRAM_ID, SESSION_ID, 0)

        assert cycle.is_full is True
        assert cycle.offer() == QuotaExhausted(PROGRAM_ID, SESSION_ID, 0)
        assert cycle.offers_made == 0

    def test_asking_a_full_cycle_again_changes_nothing(self) -> None:
        """A full cycle does not get fuller. ``MakeOfferToApplicant`` will ask in a loop."""
        cycle = a_full_cycle(quota=2)

        outcomes = [cycle.offer() for _ in range(5)]

        assert all(isinstance(outcome, QuotaExhausted) for outcome in outcomes)
        assert cycle.offers_made == 2


class TestQuotaExhaustedIsAnOutcome:
    """CLAUDE.md section 3: quota-full is "a normal domain outcome, not an error"."""

    def test_a_full_cycle_answers_rather_than_raising(self) -> None:
        cycle = a_full_cycle(quota=1)

        outcome = cycle.offer()

        assert not isinstance(outcome, Exception)
        assert not isinstance(outcome, AdmissionsError)

    def test_the_outcome_says_which_cycle_was_full_and_how_full(self) -> None:
        """The caller must not have to go back to an aggregate that may have moved on."""
        outcome = a_full_cycle(quota=4).offer()

        assert outcome == QuotaExhausted(program_id=PROGRAM_ID, session_id=SESSION_ID, quota=4)

    def test_a_recorded_offer_counts_itself(self) -> None:
        cycle = a_cycle(quota=10, offers_made=6)

        outcome = cycle.offer()

        assert outcome == OfferRecorded(
            program_id=PROGRAM_ID, session_id=SESSION_ID, offers_made=7, quota=10
        )


class TestReleasingAPlace:
    """A declined offer gives its place back, which is the decision this counterpart encodes.

    Confirmed institutional fact (CLAUDE.md section 6): ``offers_made`` counts places *held*,
    not offers ever posted. Without the release a program under-admits by exactly its decline
    rate, and with offers made automatically there is no officer working the list who would
    notice.
    """

    def test_a_released_place_is_available_again(self) -> None:
        cycle = a_cycle(quota=3, offers_made=2)

        cycle.release()

        assert (cycle.offers_made, cycle.places_remaining) == (1, 2)

    def test_a_full_cycle_offers_again_once_a_place_comes_back(self) -> None:
        """The point of the whole exercise: the freed place reaches the next candidate."""
        cycle = a_full_cycle(quota=1)
        assert isinstance(cycle.offer(), QuotaExhausted)

        cycle.release()

        assert isinstance(cycle.offer(), OfferRecorded)

    def test_releasing_every_place_empties_the_cycle(self) -> None:
        cycle = a_full_cycle(quota=3)

        for _ in range(3):
            cycle.release()

        assert (cycle.offers_made, cycle.is_full) == (0, False)

    def test_releasing_a_place_nobody_holds_is_refused(self) -> None:
        """Not an outcome like ``QuotaExhausted``: there is no second answer to give. A cycle
        asked for a place it never claimed has a caller that lost track of who holds what,
        and flooring silently at zero would turn that into a quota that quietly grew."""
        with pytest.raises(InvalidOffersMadeError, match=PROGRAM_ID):
            a_cycle(quota=3).release()

    def test_releasing_never_raises_the_quota(self) -> None:
        cycle = a_cycle(quota=2, offers_made=1)

        cycle.release()

        assert cycle.quota == 2
