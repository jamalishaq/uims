"""Lecturer-course assignments.

Assignments are scoped to a session, so teaching a course once does not confer
authority over it in perpetuity.
"""

import pytest

from faculty_department.domain import (
    CourseAssignment,
    DuplicateCourseAssignmentError,
    Lecturer,
    LecturerNotAssignedToCourseError,
    MissingIdentifierError,
)


def a_lecturer() -> Lecturer:
    return Lecturer("lec-001", "dept-csc", "Dr Adaeze Okonkwo")


class TestLecturer:
    def test_starts_with_no_courses(self) -> None:
        assert a_lecturer().assignments == frozenset()

    def test_cannot_be_built_with_a_blank_identifier(self) -> None:
        with pytest.raises(MissingIdentifierError):
            Lecturer("", "dept-csc", "Dr Adaeze Okonkwo")

    def test_belongs_to_a_department(self) -> None:
        assert a_lecturer().department_id == "dept-csc"


class TestCourseAssignment:
    def test_assigning_a_course_records_it_for_that_session(self) -> None:
        lecturer = a_lecturer()

        assignment = lecturer.assign_to_course("csc-101", "sess-2026")

        assert assignment == CourseAssignment(course_id="csc-101", session_id="sess-2026")
        assert lecturer.is_assigned_to("csc-101", "sess-2026")

    def test_assignment_does_not_carry_over_to_another_session(self) -> None:
        """Teaching CSC101 in 2026/2027 says nothing about who teaches it in 2027/2028."""
        lecturer = a_lecturer()
        lecturer.assign_to_course("csc-101", "sess-2026")

        assert not lecturer.is_assigned_to("csc-101", "sess-2027")

    def test_assignment_does_not_extend_to_another_course(self) -> None:
        lecturer = a_lecturer()
        lecturer.assign_to_course("csc-101", "sess-2026")

        assert not lecturer.is_assigned_to("csc-201", "sess-2026")

    def test_the_same_course_and_session_cannot_be_assigned_twice(self) -> None:
        lecturer = a_lecturer()
        lecturer.assign_to_course("csc-101", "sess-2026")

        with pytest.raises(DuplicateCourseAssignmentError):
            lecturer.assign_to_course("csc-101", "sess-2026")

        assert len(lecturer.assignments) == 1

    def test_a_lecturer_may_hold_several_courses(self) -> None:
        lecturer = a_lecturer()
        lecturer.assign_to_course("csc-101", "sess-2026")
        lecturer.assign_to_course("csc-201", "sess-2026")
        lecturer.assign_to_course("csc-101", "sess-2027")

        assert len(lecturer.assignments) == 3

    def test_withdrawing_removes_the_authority_to_grade(self) -> None:
        lecturer = a_lecturer()
        lecturer.assign_to_course("csc-101", "sess-2026")

        lecturer.withdraw_from_course("csc-101", "sess-2026")

        assert not lecturer.is_assigned_to("csc-101", "sess-2026")

    def test_withdrawing_from_a_course_never_held_is_an_error(self) -> None:
        with pytest.raises(LecturerNotAssignedToCourseError):
            a_lecturer().withdraw_from_course("csc-101", "sess-2026")

    def test_blank_course_or_session_is_rejected(self) -> None:
        lecturer = a_lecturer()
        with pytest.raises(MissingIdentifierError):
            lecturer.assign_to_course("  ", "sess-2026")
        with pytest.raises(MissingIdentifierError):
            lecturer.assign_to_course("csc-101", "")

    def test_the_exposed_assignment_set_cannot_grant_a_course(self) -> None:
        lecturer = a_lecturer()

        assignments = lecturer.assignments
        assert isinstance(assignments, frozenset)

        with pytest.raises(AttributeError):
            assignments.add(  # type: ignore[attr-defined]
                CourseAssignment(course_id="csc-999", session_id="sess-2026")
            )
        assert not lecturer.is_assigned_to("csc-999", "sess-2026")
