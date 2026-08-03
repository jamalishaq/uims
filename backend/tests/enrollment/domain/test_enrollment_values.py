"""``Term``, ``CreditLoadPolicy`` and the construction guards.

Zero infrastructure, as every domain test in this project is. The cases that matter are
the ones that keep an invalid value out of an aggregate: a term that cannot say which
semester it is, a cap of zero units that would let nobody register for anything.
"""

import pytest

from enrollment.domain import (
    MAX_CREDIT_UNITS_PER_SEMESTER,
    CreditLoadPolicy,
    InvalidCreditLoadPolicyError,
    InvalidCreditUnitsError,
    InvalidTermError,
    MissingIdentifierError,
    SemesterOrdinal,
    Term,
)
from enrollment.domain.values import require_credit_units, require_identifier

SESSION_ID = "sess-2026"
FIRST_SEMESTER_ID = "sem-2026-1"
SECOND_SEMESTER_ID = "sem-2026-2"


def a_term(ordinal: SemesterOrdinal = SemesterOrdinal.FIRST) -> Term:
    semester_id = FIRST_SEMESTER_ID if ordinal is SemesterOrdinal.FIRST else SECOND_SEMESTER_ID
    return Term(session_id=SESSION_ID, semester_id=semester_id, ordinal=ordinal)


class TestRequireIdentifier:
    def test_strips_surrounding_whitespace(self) -> None:
        assert require_identifier("  crs-101  ", "course_id") == "crs-101"

    @pytest.mark.parametrize("value", ["", "   ", None, 7])
    def test_rejects_anything_that_is_not_a_real_identifier(self, value: object) -> None:
        with pytest.raises(MissingIdentifierError):
            require_identifier(value, "course_id")  # type: ignore[arg-type]


class TestRequireCreditUnits:
    def test_accepts_a_whole_positive_number(self) -> None:
        assert require_credit_units(3) == 3

    def test_rejects_zero_because_a_course_worth_nothing_moves_no_cap(self) -> None:
        with pytest.raises(InvalidCreditUnitsError):
            require_credit_units(0)

    @pytest.mark.parametrize("value", [-1, 2.5, True, "3"])
    def test_rejects_anything_that_is_not_a_count_of_units(self, value: object) -> None:
        with pytest.raises(InvalidCreditUnitsError):
            require_credit_units(value)  # type: ignore[arg-type]


class TestTerm:
    def test_carries_both_ids_and_the_ordinal(self) -> None:
        term = a_term()
        assert (term.session_id, term.semester_id) == (SESSION_ID, FIRST_SEMESTER_ID)
        assert term.is_first_semester

    def test_second_semester_is_not_the_first(self) -> None:
        assert not a_term(SemesterOrdinal.SECOND).is_first_semester

    def test_two_terms_with_the_same_parts_are_the_same_term(self) -> None:
        """Equality and hashing carry weight: a term keys an offering and filters a load."""
        assert a_term() == a_term()
        assert len({a_term(), a_term(), a_term(SemesterOrdinal.SECOND)}) == 2

    def test_the_two_semesters_of_one_session_are_different_terms(self) -> None:
        assert a_term(SemesterOrdinal.FIRST) != a_term(SemesterOrdinal.SECOND)

    def test_rejects_an_ordinal_that_is_not_one(self) -> None:
        with pytest.raises(InvalidTermError):
            Term(session_id=SESSION_ID, semester_id=FIRST_SEMESTER_ID, ordinal=1)  # type: ignore[arg-type]

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_rejects_a_blank_session_or_semester(self, blank: str) -> None:
        with pytest.raises(MissingIdentifierError):
            Term(session_id=blank, semester_id=FIRST_SEMESTER_ID, ordinal=SemesterOrdinal.FIRST)
        with pytest.raises(MissingIdentifierError):
            Term(session_id=SESSION_ID, semester_id=blank, ordinal=SemesterOrdinal.FIRST)


class TestCreditLoadPolicy:
    def test_defaults_to_the_confirmed_institutional_cap(self) -> None:
        assert CreditLoadPolicy().max_units == MAX_CREDIT_UNITS_PER_SEMESTER == 24

    def test_permits_a_load_that_lands_exactly_on_the_cap(self) -> None:
        assert CreditLoadPolicy().permits(current_load=21, additional=3)

    def test_refuses_a_load_that_passes_the_cap_by_one_unit(self) -> None:
        assert not CreditLoadPolicy().permits(current_load=21, additional=4)

    def test_the_cap_is_a_construction_argument_not_a_rule(self) -> None:
        """The whole point of the value object: a policy change is an argument."""
        assert CreditLoadPolicy(max_units=15).permits(current_load=12, additional=3)
        assert not CreditLoadPolicy(max_units=15).permits(current_load=12, additional=4)

    def test_headroom_reports_what_is_left(self) -> None:
        assert CreditLoadPolicy().headroom(18) == 6

    def test_headroom_never_goes_negative(self) -> None:
        assert CreditLoadPolicy(max_units=15).headroom(21) == 0

    @pytest.mark.parametrize("cap", [0, -3, 2.5, True])
    def test_rejects_a_cap_that_is_not_a_whole_positive_number(self, cap: object) -> None:
        with pytest.raises(InvalidCreditLoadPolicyError):
            CreditLoadPolicy(max_units=cap)  # type: ignore[arg-type]
