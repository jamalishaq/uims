"""The counter invariant: a matric sequence never hands out the same ordinal twice.

This is the aggregate-level half of the concurrency requirement. It is tested here, with
no ports and no use case in the way, because the guarantee has to hold in the aggregate
itself — a use case that happened to be single-threaded today would hide a sequence that
was never safe.
"""

from concurrent.futures import ThreadPoolExecutor

import pytest

from student_profile.domain import (
    DepartmentCode,
    EntryYear,
    InvalidSequenceStateError,
    MatricSequence,
)

CSC = DepartmentCode("0591")
YEAR_2026 = EntryYear(2026)

CONCURRENT_CLAIMS = 200
"""Enough threads to interleave a read-then-write reliably on a naive implementation."""


class TestStartingAndRestoring:
    def test_a_new_sequence_has_issued_nothing(self) -> None:
        sequence = MatricSequence.start(CSC, YEAR_2026)

        assert sequence.issued == 0
        assert sequence.department_code == CSC
        assert sequence.entry_year == YEAR_2026

    def test_a_sequence_is_identified_by_its_department_and_year(self) -> None:
        assert MatricSequence.start(CSC, YEAR_2026).key == ("0591", 2026)

    def test_a_stored_sequence_resumes_where_it_left_off(self) -> None:
        """Phase 6's adapter rebuilds counters this way; resuming at 0 would re-issue."""
        resumed = MatricSequence.restore(CSC, YEAR_2026, issued=317)

        assert resumed.take_next() == 318

    @pytest.mark.parametrize("issued", [-1, "5", 5.0, None, True])
    def test_a_count_that_cannot_have_happened_is_rejected(self, issued: object) -> None:
        with pytest.raises(InvalidSequenceStateError):
            MatricSequence.restore(CSC, YEAR_2026, issued)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        ("code", "year"),
        [("0591", YEAR_2026), (CSC, 2026), ("CSC", "2026")],
    )
    def test_a_sequence_cannot_be_built_from_raw_values(self, code: object, year: object) -> None:
        """The value objects are the validation; accepting strings would route around it."""
        with pytest.raises(InvalidSequenceStateError):
            MatricSequence(code, year)  # type: ignore[arg-type]


class TestTakingNumbers:
    def test_the_first_ordinal_is_one(self) -> None:
        """A place in an intake, not an index: there is no zeroth student."""
        assert MatricSequence.start(CSC, YEAR_2026).take_next() == 1

    def test_ordinals_come_out_in_order(self) -> None:
        sequence = MatricSequence.start(CSC, YEAR_2026)

        assert [sequence.take_next() for _ in range(5)] == [1, 2, 3, 4, 5]

    def test_the_issued_count_is_what_has_been_handed_out(self) -> None:
        sequence = MatricSequence.start(CSC, YEAR_2026)
        for _ in range(3):
            sequence.take_next()

        assert sequence.issued == 3

    def test_two_departments_count_separately(self) -> None:
        csc = MatricSequence.start(CSC, YEAR_2026)
        mcb = MatricSequence.start(DepartmentCode("0672"), YEAR_2026)
        csc.take_next()

        assert mcb.take_next() == 1

    def test_two_years_count_separately(self) -> None:
        first = MatricSequence.start(CSC, YEAR_2026)
        second = MatricSequence.start(CSC, EntryYear(2027))
        first.take_next()

        assert second.take_next() == 1


class TestConcurrentClaims:
    """The invariant that matters: no two claimants may receive the same ordinal."""

    def test_every_concurrent_claim_gets_a_distinct_ordinal(self) -> None:
        sequence = MatricSequence.start(CSC, YEAR_2026)

        with ThreadPoolExecutor(max_workers=16) as pool:
            claimed = list(pool.map(lambda _: sequence.take_next(), range(CONCURRENT_CLAIMS)))

        assert len(set(claimed)) == CONCURRENT_CLAIMS

    def test_concurrent_claims_leave_no_gaps_either(self) -> None:
        """Distinctness alone would be satisfiable by skipping numbers; this pins both."""
        sequence = MatricSequence.start(CSC, YEAR_2026)

        with ThreadPoolExecutor(max_workers=16) as pool:
            claimed = list(pool.map(lambda _: sequence.take_next(), range(CONCURRENT_CLAIMS)))

        assert sorted(claimed) == list(range(1, CONCURRENT_CLAIMS + 1))

    def test_the_count_agrees_with_what_was_handed_out(self) -> None:
        sequence = MatricSequence.start(CSC, YEAR_2026)

        with ThreadPoolExecutor(max_workers=16) as pool:
            list(pool.map(lambda _: sequence.take_next(), range(CONCURRENT_CLAIMS)))

        assert sequence.issued == CONCURRENT_CLAIMS
