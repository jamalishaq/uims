"""``CourseOffering``: seats, and the invariant that there are never more students than them.

The boundary is the test that matters. A claim at capacity-1 must succeed and a claim at
capacity must change nothing at all — an offering that quietly incremented past its own
capacity would put a student in a room with no chair, and nothing downstream would notice
until the lecture.
"""

import pytest

from enrollment.domain import (
    CapacityExhausted,
    CourseOffering,
    InvalidCapacityError,
    InvalidSeatsTakenError,
    InvalidTermError,
    MissingIdentifierError,
    SeatClaimed,
    SemesterOrdinal,
    Term,
)

COURSE_ID = "crs-csc101"
TERM = Term(session_id="sess-2026", semester_id="sem-2026-1", ordinal=SemesterOrdinal.FIRST)


class TestOpening:
    def test_a_new_offering_has_every_seat_free(self) -> None:
        offering = CourseOffering.open(COURSE_ID, TERM, capacity=40)
        assert (offering.seats_taken, offering.seats_remaining) == (0, 40)
        assert not offering.is_full

    def test_a_capacity_of_zero_is_full_from_the_moment_it_opens(self) -> None:
        """A course listed but not run: truthful, and needs no second notion of 'closed'."""
        offering = CourseOffering.open(COURSE_ID, TERM, capacity=0)
        assert offering.is_full
        assert isinstance(offering.claim_seat(), CapacityExhausted)

    def test_can_be_rebuilt_partway_through_registration(self) -> None:
        """What a repository does when it reads one back: state, not a fresh start."""
        offering = CourseOffering(COURSE_ID, TERM, 40, seats_taken=39)
        assert offering.seats_remaining == 1

    @pytest.mark.parametrize("capacity", [-1, 2.5, True, "40"])
    def test_rejects_a_capacity_that_is_not_a_count_of_seats(self, capacity: object) -> None:
        with pytest.raises(InvalidCapacityError):
            CourseOffering.open(COURSE_ID, TERM, capacity=capacity)  # type: ignore[arg-type]

    def test_rejects_more_seats_taken_than_there_are_seats(self) -> None:
        with pytest.raises(InvalidSeatsTakenError):
            CourseOffering(COURSE_ID, TERM, 40, seats_taken=41)

    def test_rejects_a_negative_number_of_seats_taken(self) -> None:
        with pytest.raises(InvalidSeatsTakenError):
            CourseOffering(COURSE_ID, TERM, 40, seats_taken=-1)

    def test_rejects_a_blank_course(self) -> None:
        with pytest.raises(MissingIdentifierError):
            CourseOffering.open("  ", TERM, capacity=40)

    def test_rejects_a_term_that_is_not_one(self) -> None:
        with pytest.raises(InvalidTermError):
            CourseOffering.open(COURSE_ID, "sem-2026-1", capacity=40)  # type: ignore[arg-type]


class TestClaimingSeats:
    def test_a_claim_takes_one_seat_and_reports_the_new_count(self) -> None:
        offering = CourseOffering.open(COURSE_ID, TERM, capacity=40)
        outcome = offering.claim_seat()
        assert isinstance(outcome, SeatClaimed)
        assert (outcome.seats_taken, outcome.capacity) == (1, 40)
        assert (offering.seats_taken, offering.seats_remaining) == (1, 39)

    def test_the_last_seat_is_claimable(self) -> None:
        """The boundary from below: capacity-1 taken still leaves one."""
        offering = CourseOffering(COURSE_ID, TERM, 40, seats_taken=39)
        assert isinstance(offering.claim_seat(), SeatClaimed)
        assert offering.is_full
        assert offering.seats_remaining == 0

    def test_claiming_past_the_last_seat_changes_nothing(self) -> None:
        """The boundary from above, and the invariant: full does not become fuller."""
        offering = CourseOffering(COURSE_ID, TERM, 40, seats_taken=40)
        outcome = offering.claim_seat()
        assert isinstance(outcome, CapacityExhausted)
        assert (outcome.course_id, outcome.term, outcome.capacity) == (COURSE_ID, TERM, 40)
        assert offering.seats_taken == 40

    def test_a_full_offering_says_the_same_thing_however_often_it_is_asked(self) -> None:
        offering = CourseOffering(COURSE_ID, TERM, 1, seats_taken=1)
        assert all(isinstance(offering.claim_seat(), CapacityExhausted) for _ in range(3))
        assert offering.seats_taken == 1

    def test_claims_never_exceed_capacity_however_many_are_made(self) -> None:
        """The invariant this aggregate exists for, asserted directly."""
        offering = CourseOffering.open(COURSE_ID, TERM, capacity=3)
        claimed = [offering.claim_seat() for _ in range(10)]
        assert sum(isinstance(outcome, SeatClaimed) for outcome in claimed) == 3
        assert offering.seats_taken == offering.capacity == 3

    def test_the_outcome_carries_the_numbers_the_decision_was_made_on(self) -> None:
        """A caller can report which offering filled up without going back to the aggregate."""
        offering = CourseOffering.open(COURSE_ID, TERM, capacity=1)
        claimed = offering.claim_seat()
        assert isinstance(claimed, SeatClaimed)
        assert claimed.course_id == COURSE_ID
        assert claimed.term == TERM
