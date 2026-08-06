"""A lecturer's staff record: rank, employment status, and the degrees they hold.

The decision under test is that **none of these has a default**. A rank invented here would be
baked into every staff record and would be invisible — a lecturer defaulted to Lecturer II
reads identically to one somebody checked — so ``None`` means "not recorded" and says so.

``Rank`` and ``EmploymentStatus`` are enums because the university defines those sets.
``degree`` is free text because nobody defines the set of degrees the world can award, and an
enum that rejected ``MBBS`` would force whoever entered it to pick something wrong.

Zero infrastructure: one aggregate, no repository, no ports.
"""

from datetime import date

import pytest

from faculty_department.domain import (
    EmploymentStatus,
    InvalidLecturerProfileError,
    InvalidQualificationError,
    Lecturer,
    MissingIdentifierError,
    Qualification,
    Rank,
)

PHD = Qualification(
    degree="PhD", discipline="Computer Science", institution="University of Ibadan", year=2014
)
MSC = Qualification(
    degree="M.Sc", discipline="Computer Science", institution="University of Lagos", year=2009
)


def a_lecturer(**overrides: object) -> Lecturer:
    fields: dict[str, object] = {
        "lecturer_id": "lec-001",
        "department_id": "dept-csc",
        "full_name": "Dr Adaeze Okonkwo",
    }
    fields.update(overrides)
    return Lecturer(**fields)  # type: ignore[arg-type]


class TestAnUnrecordedProfile:
    def test_a_new_lecturer_has_no_rank_and_no_status(self) -> None:
        """``None`` is a statement about the data, not a default standing in for one."""
        lecturer = a_lecturer()

        assert lecturer.rank is None
        assert lecturer.employment_status is None
        assert lecturer.qualifications == ()

    def test_a_lecturer_can_be_created_with_a_full_record(self) -> None:
        lecturer = a_lecturer(
            rank=Rank.SENIOR_LECTURER,
            employment_status=EmploymentStatus.FULL_TIME,
            qualifications=[PHD, MSC],
        )

        assert lecturer.rank is Rank.SENIOR_LECTURER
        assert lecturer.employment_status is EmploymentStatus.FULL_TIME
        assert lecturer.qualifications == (PHD, MSC)

    def test_qualifications_keep_the_order_they_were_entered(self) -> None:
        """Order means nothing but it is somebody's record; re-ordering it rewrites theirs."""
        assert a_lecturer(qualifications=[MSC, PHD]).qualifications == (MSC, PHD)

    def test_qualifications_are_a_tuple_callers_cannot_extend(self) -> None:
        assert isinstance(a_lecturer(qualifications=[PHD]).qualifications, tuple)


class TestAmendingTheProfile:
    def test_it_replaces_what_is_on_file(self) -> None:
        lecturer = a_lecturer(rank=Rank.LECTURER_II, qualifications=[MSC])

        lecturer.amend_profile(
            rank=Rank.SENIOR_LECTURER,
            employment_status=EmploymentStatus.CONTRACT,
            qualifications=[MSC, PHD],
        )

        assert lecturer.rank is Rank.SENIOR_LECTURER
        assert lecturer.employment_status is EmploymentStatus.CONTRACT
        assert lecturer.qualifications == (MSC, PHD)

    def test_omitting_a_field_clears_it(self) -> None:
        """This is a replacement, which is what the form behind it does."""
        lecturer = a_lecturer(
            rank=Rank.PROFESSOR,
            employment_status=EmploymentStatus.FULL_TIME,
            qualifications=[PHD],
        )

        lecturer.amend_profile()

        assert (lecturer.rank, lecturer.employment_status, lecturer.qualifications) == (
            None,
            None,
            (),
        )

    def test_it_does_not_touch_identity_or_teaching(self) -> None:
        """A staff record is not a transfer and not a timetable."""
        lecturer = a_lecturer()
        lecturer.assign_to_course("CSC101", "sess-2026")

        lecturer.amend_profile(rank=Rank.READER)

        assert lecturer.department_id == "dept-csc"
        assert lecturer.full_name == "Dr Adaeze Okonkwo"
        assert lecturer.is_assigned_to("CSC101", "sess-2026")


class TestWhatARecordRefuses:
    def test_the_same_degree_twice_is_a_slip_rather_than_two_degrees(self) -> None:
        with pytest.raises(InvalidLecturerProfileError, match="more than once"):
            a_lecturer(qualifications=[PHD, PHD])

    def test_a_rank_that_is_not_a_rank_is_refused(self) -> None:
        with pytest.raises(InvalidLecturerProfileError, match="rank"):
            a_lecturer(rank="professor")

    def test_an_employment_status_that_is_not_one_is_refused(self) -> None:
        with pytest.raises(InvalidLecturerProfileError, match="employment_status"):
            a_lecturer(employment_status="full-time")

    def test_something_that_is_not_a_qualification_is_refused(self) -> None:
        with pytest.raises(InvalidLecturerProfileError, match="Qualification"):
            a_lecturer(qualifications=["PhD"])


class TestAQualification:
    def test_it_reads_back_as_a_sentence(self) -> None:
        assert str(PHD) == "PhD Computer Science, University of Ibadan (2014)"

    @pytest.mark.parametrize("field", ["degree", "discipline", "institution"])
    def test_every_text_field_is_required(self, field: str) -> None:
        fields = {
            "degree": "PhD",
            "discipline": "Computer Science",
            "institution": "University of Ibadan",
            "year": 2014,
        }
        fields[field] = "  "
        with pytest.raises(MissingIdentifierError):
            Qualification(**fields)  # type: ignore[arg-type]

    def test_a_degree_awarded_in_the_future_is_refused(self) -> None:
        """``BioData``'s argument about dates of birth: the one cross-field check that is ours."""
        with pytest.raises(InvalidQualificationError):
            Qualification("PhD", "Computer Science", "Ibadan", date.today().year + 1)

    def test_an_implausibly_old_degree_is_refused(self) -> None:
        with pytest.raises(InvalidQualificationError):
            Qualification("PhD", "Computer Science", "Ibadan", 1712)

    def test_a_year_that_is_not_a_number_is_refused(self) -> None:
        with pytest.raises(InvalidQualificationError):
            Qualification("PhD", "Computer Science", "Ibadan", True)

    def test_free_text_degrees_the_world_actually_awards_are_accepted(self) -> None:
        """The reason ``degree`` is not an enum: an enum would have to know all of these."""
        for degree in ("MBBS", "M.Eng", "B.A. (Hons)", "LL.B", "PGDE"):
            assert Qualification(degree, "Medicine", "LASU", 2010).degree == degree
