"""What an application is made of: bio-data, and a UTME result that is whole.

These are the guards standing between a half-entered JAMB form and every screening
decision made downstream. A result that could be constructed with three subjects, or with
Chemistry listed twice, would push "what does that mean?" onto every rule that reads it.

Zero infrastructure: value objects, and nothing else.
"""

from datetime import date, timedelta

import pytest

from admissions.domain import (
    BioData,
    InvalidBioDataError,
    InvalidUtmeResultError,
    InvalidUtmeScoreError,
    MissingIdentifierError,
    UtmeResult,
    UtmeSubjectScore,
)

SUBJECTS = ("USE OF ENGLISH", "MATHEMATICS", "PHYSICS", "CHEMISTRY")


def a_utme_result(*scores: int) -> UtmeResult:
    """A four-subject result, scoring 70 in each subject unless told otherwise."""
    marks = scores or (70, 70, 70, 70)
    return UtmeResult(
        tuple(
            UtmeSubjectScore(subject, mark) for subject, mark in zip(SUBJECTS, marks, strict=True)
        )
    )


class TestUtmeSubjectScore:
    def test_a_subject_is_held_upper_cased_and_stripped(self) -> None:
        score = UtmeSubjectScore("  Use of English  ", 78)

        assert score.subject == "USE OF ENGLISH"
        assert score.score == 78

    @pytest.mark.parametrize("mark", [0, 100])
    def test_the_range_is_inclusive_at_both_ends(self, mark: int) -> None:
        assert UtmeSubjectScore("PHYSICS", mark).score == mark

    @pytest.mark.parametrize("mark", [-1, 101, 400])
    def test_a_score_outside_zero_to_one_hundred_is_rejected(self, mark: int) -> None:
        with pytest.raises(InvalidUtmeScoreError):
            UtmeSubjectScore("PHYSICS", mark)

    @pytest.mark.parametrize("mark", ["70", 70.5, None, True])
    def test_a_score_that_is_not_a_whole_number_is_rejected(self, mark: object) -> None:
        """``True`` is an int to Python and a data-entry accident to an admissions office."""
        with pytest.raises(InvalidUtmeScoreError):
            UtmeSubjectScore("PHYSICS", mark)  # type: ignore[arg-type]

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_a_blank_subject_is_rejected(self, blank: str) -> None:
        with pytest.raises(MissingIdentifierError):
            UtmeSubjectScore(blank, 70)

    def test_two_scores_for_the_same_subject_and_mark_are_the_same_value(self) -> None:
        assert UtmeSubjectScore("physics", 70) == UtmeSubjectScore("PHYSICS", 70)


class TestUtmeResult:
    def test_a_result_reports_its_subjects_and_aggregate(self) -> None:
        result = a_utme_result(78, 65, 70, 62)

        assert result.subjects == frozenset(SUBJECTS)
        assert result.aggregate == 275

    def test_the_aggregate_is_derived_from_the_scores_it_holds(self) -> None:
        """Never stored: a total that can drift from its parts is a second source of truth."""
        assert a_utme_result(0, 0, 0, 0).aggregate == 0
        assert a_utme_result(100, 100, 100, 100).aggregate == 400

    def test_a_score_can_be_looked_up_by_subject(self) -> None:
        result = a_utme_result(78, 65, 70, 62)

        assert result.score_for("mathematics") == 65
        assert result.score_for("BIOLOGY") is None

    def test_any_iterable_of_scores_becomes_a_tuple(self) -> None:
        result = UtmeResult([UtmeSubjectScore(subject, 70) for subject in SUBJECTS])

        assert isinstance(result.scores, tuple)

    @pytest.mark.parametrize("count", [0, 3, 5])
    def test_a_result_must_carry_exactly_four_subjects(self, count: int) -> None:
        scores = tuple(UtmeSubjectScore(f"SUBJECT {n}", 70) for n in range(count))

        with pytest.raises(InvalidUtmeResultError):
            UtmeResult(scores)

    def test_the_same_subject_cannot_be_listed_twice(self) -> None:
        """One score counted against two requirements is how an unqualified applicant gets in."""
        scores = (
            UtmeSubjectScore("USE OF ENGLISH", 78),
            UtmeSubjectScore("CHEMISTRY", 65),
            UtmeSubjectScore("chemistry", 70),
            UtmeSubjectScore("PHYSICS", 62),
        )

        with pytest.raises(InvalidUtmeResultError):
            UtmeResult(scores)

    def test_a_result_is_made_of_subject_scores_and_not_bare_numbers(self) -> None:
        with pytest.raises(InvalidUtmeResultError):
            UtmeResult((78, 65, 70, 62))  # type: ignore[arg-type]


class TestBioData:
    def test_a_name_is_stripped_and_the_rest_is_optional(self) -> None:
        bio = BioData("  Adaeze Okonkwo  ")

        assert bio.full_name == "Adaeze Okonkwo"
        assert bio.date_of_birth is None
        assert bio.email is None
        assert bio.phone_number is None

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_a_blank_name_is_rejected(self, blank: str) -> None:
        with pytest.raises(MissingIdentifierError):
            BioData(blank)

    @pytest.mark.parametrize("field", ["email", "phone_number"])
    def test_an_optional_field_may_be_absent_but_not_blank(self, field: str) -> None:
        """Absent is a normal record; three spaces is a data-entry accident."""
        assert getattr(BioData("Adaeze Okonkwo", **{field: None}), field) is None

        with pytest.raises(MissingIdentifierError):
            BioData("Adaeze Okonkwo", **{field: "   "})

    def test_nobody_was_born_in_the_future(self) -> None:
        with pytest.raises(InvalidBioDataError):
            BioData("Adaeze Okonkwo", date_of_birth=date.today() + timedelta(days=1))

    def test_a_date_of_birth_must_be_a_date(self) -> None:
        with pytest.raises(InvalidBioDataError):
            BioData("Adaeze Okonkwo", date_of_birth="2006-04-01")  # type: ignore[arg-type]
