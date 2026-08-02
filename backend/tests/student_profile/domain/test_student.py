"""The ``Student`` aggregate — and what it deliberately does not know.

Half of these tests are about absence. This context is the identity anchor (CLAUDE.md
section 3), and the temptation with an identity anchor is to let every other context keep
its copy of the truth here. A test that pins the aggregate as thin is what makes that
temptation visible when someone gives in to it.
"""

from datetime import date

import pytest

from student_profile.domain import (
    BioData,
    InvalidBioDataError,
    InvalidLevelError,
    InvalidMatricNumberError,
    Level,
    MatricNumber,
    MissingIdentifierError,
    Student,
)

MATRIC = MatricNumber("260591001")
BIO = BioData(full_name="Adaeze Okonkwo", date_of_birth=date(2008, 4, 17))
PROGRAM_ID = "prog-csc-bsc"
SESSION_ID = "sess-2026"


def a_student(**overrides: object) -> Student:
    fields: dict[str, object] = {
        "student_id": "stu-0001",
        "matric_number": MATRIC,
        "bio_data": BIO,
        "program_id": PROGRAM_ID,
        "entry_session_id": SESSION_ID,
        "entry_level": Level(100),
    }
    fields.update(overrides)
    return Student(**fields)  # type: ignore[arg-type]


class TestCreation:
    def test_a_student_holds_the_identity_other_contexts_quote(self) -> None:
        student = a_student()

        assert student.student_id == "stu-0001"
        assert student.matric_number == MATRIC
        assert student.bio_data == BIO
        assert student.program_id == PROGRAM_ID
        assert student.entry_session_id == SESSION_ID
        assert student.entry_level == Level(100)

    def test_a_student_registered_by_hand_has_no_applicant(self) -> None:
        assert a_student().applicant_id is None

    def test_a_matriculated_student_remembers_the_applicant_they_were(self) -> None:
        """Billing opened an account under that applicant id before this student existed,
        and this is the only record of which account belongs to which matric number."""
        assert a_student(applicant_id="app-77").applicant_id == "app-77"

    def test_direct_entry_starts_above_the_first_level(self) -> None:
        assert a_student(entry_level=Level(200)).entry_level == Level(200)

    @pytest.mark.parametrize(
        "field", ["student_id", "program_id", "entry_session_id", "applicant_id"]
    )
    def test_a_blank_identifier_is_rejected(self, field: str) -> None:
        with pytest.raises(MissingIdentifierError):
            a_student(**{field: "   "})

    def test_a_matric_number_cannot_be_a_bare_string(self) -> None:
        """It has to have come from the issuer. A string could have come from anywhere."""
        with pytest.raises(InvalidMatricNumberError):
            a_student(matric_number="260591001")

    def test_bio_data_cannot_be_a_bare_dict(self) -> None:
        with pytest.raises(InvalidBioDataError):
            a_student(bio_data={"full_name": "Adaeze Okonkwo"})

    def test_a_level_cannot_be_a_bare_integer(self) -> None:
        with pytest.raises(InvalidLevelError):
            a_student(entry_level=100)


class TestCorrections:
    def test_bio_data_is_restated_whole(self) -> None:
        student = a_student()
        corrected = BioData(full_name="Adaeze Okonkwo-Bello", date_of_birth=date(2008, 4, 17))

        student.correct_bio_data(corrected)

        assert student.bio_data == corrected

    def test_a_correction_must_itself_be_valid_bio_data(self) -> None:
        student = a_student()

        with pytest.raises(InvalidBioDataError):
            student.correct_bio_data("Adaeze Okonkwo-Bello")  # type: ignore[arg-type]

        assert student.bio_data == BIO


class TestWhatTheAggregateDoesNotKnow:
    """Thin on purpose. Each of these is owned by another context, and a copy here would
    be a second answer to a question that already has one."""

    @pytest.mark.parametrize(
        "attribute",
        [
            "current_level",  # a conclusion drawn from grades — Academic Records
            "cgpa",  # Academic Records
            "balance",  # Billing
            "enrollments",  # Enrollment
            "courses",  # Enrollment
            "department_id",  # Faculty & Department, reachable through the program
        ],
    )
    def test_it_is_not_here(self, attribute: str) -> None:
        assert not hasattr(a_student(), attribute)

    def test_a_matric_number_cannot_be_reassigned(self) -> None:
        """Not an oversight: reissuing is a new identity, not a correction, and every
        context holding the old number would have to be told."""
        student = a_student()

        assert not hasattr(student, "reissue_matric_number")
        with pytest.raises(AttributeError):
            student.matric_number = MatricNumber("260591002")  # type: ignore[misc]
