"""What a ``Course`` will and will not let you say about it.

Zero infrastructure: no repository, no ports, no fixtures beyond a builder. If a test
in this file ever needs one, business rules have leaked out of the domain layer.
"""

from typing import Any

import pytest

from course_catalog.domain import (
    Course,
    DuplicatePrerequisiteError,
    InvalidCreditUnitsError,
    MissingIdentifierError,
    PrerequisiteNotRequiredError,
    SelfPrerequisiteError,
)

COURSE_ID = "crs-csc-101"
DEPARTMENT_ID = "dept-csc"


def a_course(
    course_id: str = COURSE_ID,
    department_id: str = DEPARTMENT_ID,
    code: str = "CSC101",
    title: str = "Introduction to Computer Science",
    credit_units: int = 3,
) -> Course:
    return Course.create(course_id, department_id, code, title, credit_units)


class TestConstruction:
    def test_a_course_keeps_what_it_was_given(self) -> None:
        course = a_course()

        assert course.course_id == COURSE_ID
        assert course.department_id == DEPARTMENT_ID
        assert course.code == "CSC101"
        assert course.title == "Introduction to Computer Science"
        assert course.credit_units == 3

    def test_a_new_course_is_active_and_requires_nothing(self) -> None:
        course = a_course()

        assert course.is_active is True
        assert course.prerequisite_ids == ()

    def test_code_is_normalised_to_upper_case(self) -> None:
        assert a_course(code="csc101").code == "CSC101"

    def test_surrounding_whitespace_is_stripped(self) -> None:
        course = a_course(code="  csc101  ", title="  Intro  ")

        assert course.code == "CSC101"
        assert course.title == "Intro"

    @pytest.mark.parametrize("field", ["course_id", "department_id", "code", "title"])
    @pytest.mark.parametrize("blank", ["", "   "])
    def test_a_blank_text_field_is_refused(self, field: str, blank: str) -> None:
        with pytest.raises(MissingIdentifierError):
            a_course(**{field: blank})

    @pytest.mark.parametrize("units", [0, -1, -3, 2.5, "3", True, None])
    def test_credit_units_must_be_a_whole_number_of_units(self, units: Any) -> None:
        """``True`` is in here on purpose: in Python it is also the integer 1."""
        with pytest.raises(InvalidCreditUnitsError):
            a_course(credit_units=units)

    def test_one_credit_unit_is_allowed(self) -> None:
        """The floor is one, not three. There is no ceiling — see values.py."""
        assert a_course(credit_units=1).credit_units == 1

    def test_a_course_can_be_built_with_prerequisites_already_in_place(self) -> None:
        """The repository needs this to reconstitute a stored course."""
        course = Course(
            COURSE_ID,
            DEPARTMENT_ID,
            "CSC301",
            "Algorithms",
            3,
            prerequisite_ids=("crs-csc-201", "crs-mth-101"),
        )

        assert course.prerequisite_ids == ("crs-csc-201", "crs-mth-101")

    def test_reconstitution_applies_the_same_rules_as_wiring_one_in(self) -> None:
        with pytest.raises(SelfPrerequisiteError):
            Course(COURSE_ID, DEPARTMENT_ID, "CSC101", "Intro", 3, prerequisite_ids=(COURSE_ID,))


class TestPrerequisites:
    def test_a_course_cannot_require_itself(self) -> None:
        """The verification criterion: a direct self-prerequisite is a domain error."""
        course = a_course()

        with pytest.raises(SelfPrerequisiteError):
            course.add_prerequisite(COURSE_ID)

        assert course.prerequisite_ids == ()

    def test_a_course_can_require_another_course(self) -> None:
        course = a_course("crs-csc-201")

        course.add_prerequisite(COURSE_ID)

        assert course.requires(COURSE_ID)
        assert course.prerequisite_ids == (COURSE_ID,)

    def test_prerequisites_keep_the_order_they_were_added(self) -> None:
        course = a_course("crs-csc-301")

        course.add_prerequisite("crs-csc-201")
        course.add_prerequisite("crs-mth-101")

        assert course.prerequisite_ids == ("crs-csc-201", "crs-mth-101")

    def test_the_same_prerequisite_cannot_be_added_twice(self) -> None:
        course = a_course("crs-csc-201")
        course.add_prerequisite(COURSE_ID)

        with pytest.raises(DuplicatePrerequisiteError):
            course.add_prerequisite(COURSE_ID)

        assert course.prerequisite_ids == (COURSE_ID,)

    def test_a_blank_prerequisite_id_is_refused(self) -> None:
        course = a_course("crs-csc-201")

        with pytest.raises(MissingIdentifierError):
            course.add_prerequisite("   ")

    def test_a_prerequisite_can_be_dropped(self) -> None:
        course = a_course("crs-csc-201")
        course.add_prerequisite(COURSE_ID)

        course.remove_prerequisite(COURSE_ID)

        assert course.requires(COURSE_ID) is False
        assert course.prerequisite_ids == ()

    def test_dropping_a_prerequisite_the_course_never_had_is_refused(self) -> None:
        course = a_course("crs-csc-201")

        with pytest.raises(PrerequisiteNotRequiredError):
            course.remove_prerequisite(COURSE_ID)

    def test_the_prerequisite_list_handed_out_is_a_copy(self) -> None:
        """Callers cannot reach in and rewrite the catalog's prerequisites."""
        course = a_course("crs-csc-201")
        course.add_prerequisite(COURSE_ID)

        handed_out = list(course.prerequisite_ids)
        handed_out.append("crs-smuggled-in")

        assert course.prerequisite_ids == (COURSE_ID,)


class TestAmendments:
    def test_a_course_can_be_retitled(self) -> None:
        course = a_course()

        course.retitle("Introduction to Computing")

        assert course.title == "Introduction to Computing"

    def test_a_blank_title_is_refused_and_the_old_one_survives(self) -> None:
        course = a_course()

        with pytest.raises(MissingIdentifierError):
            course.retitle("  ")

        assert course.title == "Introduction to Computer Science"

    def test_credit_units_can_be_corrected(self) -> None:
        course = a_course()

        course.set_credit_units(4)

        assert course.credit_units == 4

    def test_invalid_credit_units_are_refused_and_the_old_value_survives(self) -> None:
        course = a_course()

        with pytest.raises(InvalidCreditUnitsError):
            course.set_credit_units(0)

        assert course.credit_units == 3

    def test_a_course_can_move_to_another_department(self) -> None:
        course = a_course()

        course.transfer_to_department("dept-swe")

        assert course.department_id == "dept-swe"


class TestRetirement:
    def test_a_retired_course_is_no_longer_active(self) -> None:
        course = a_course()

        course.retire()

        assert course.is_active is False

    def test_a_retired_course_keeps_everything_else(self) -> None:
        """Retiring says "stop offering this", not "forget this"."""
        course = a_course("crs-csc-201")
        course.add_prerequisite(COURSE_ID)

        course.retire()

        assert course.code == "CSC101"
        assert course.credit_units == 3
        assert course.prerequisite_ids == (COURSE_ID,)

    def test_a_retired_course_can_come_back(self) -> None:
        course = a_course()
        course.retire()

        course.reinstate()

        assert course.is_active is True

    def test_retiring_twice_is_not_an_error(self) -> None:
        course = a_course()

        course.retire()
        course.retire()

        assert course.is_active is False
