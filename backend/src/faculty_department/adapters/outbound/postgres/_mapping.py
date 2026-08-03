"""Rows to aggregates and back, written out rather than mapped.

The direction that matters is the one *into* the domain. Going out is a matter of reading
properties; coming in, every aggregate has to arrive through a constructor that validates,
because "an entity must never be constructible into an invalid state" (CLAUDE.md section 4)
does not stop being true because the values came from a table this system wrote.

Four of the five reconstitute through their ordinary public constructors —
``Program(admitting=...)`` and ``Lecturer`` plus ``assign_to_course`` say everything a stored
row holds. ``Session`` cannot: its status is reachable only through ``open`` and ``close``,
and replaying ``open`` on load would return a ``SessionOpened`` for a session that opened last
September. That is what ``Session.restore`` is for, and it is the only new door this context
opens.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import Row, Table

from faculty_department.domain.department import Department
from faculty_department.domain.faculty import Faculty
from faculty_department.domain.lecturer import Lecturer
from faculty_department.domain.program import Program
from faculty_department.domain.session import (
    Semester,
    SemesterOrdinal,
    Session,
    SessionStatus,
)
from faculty_department.domain.values import AcademicYear


def faculty_row(faculty: Faculty) -> dict[str, Any]:
    return {"faculty_id": faculty.faculty_id, "name": faculty.name, "code": faculty.code}


def to_faculty(row: Row[Any]) -> Faculty:
    return Faculty(row.faculty_id, row.name, row.code)


def department_row(department: Department) -> dict[str, Any]:
    return {
        "department_id": department.department_id,
        "faculty_id": department.faculty_id,
        "name": department.name,
        "code": department.code,
    }


def to_department(row: Row[Any]) -> Department:
    return Department(row.department_id, row.faculty_id, row.name, row.code)


def program_row(program: Program) -> dict[str, Any]:
    return {
        "program_id": program.program_id,
        "department_id": program.department_id,
        "name": program.name,
        "code": program.code,
        "admitting": program.is_admitting,
    }


def to_program(row: Row[Any]) -> Program:
    return Program(
        row.program_id,
        row.department_id,
        row.name,
        row.code,
        admitting=row.admitting,
    )


def lecturer_row(lecturer: Lecturer) -> dict[str, Any]:
    return {
        "lecturer_id": lecturer.lecturer_id,
        "department_id": lecturer.department_id,
        "full_name": lecturer.full_name,
    }


def assignment_rows(lecturer: Lecturer) -> list[dict[str, Any]]:
    """Sorted, so two equal aggregates produce identical statements.

    The aggregate holds a ``set``, which has no order to preserve; sorting makes the write
    deterministic, which matters when reading a query log to work out what a test did.
    """
    return sorted(
        (
            {
                "lecturer_id": lecturer.lecturer_id,
                "course_id": assignment.course_id,
                "session_id": assignment.session_id,
            }
            for assignment in lecturer.assignments
        ),
        key=lambda row: (row["course_id"], row["session_id"]),
    )


def to_lecturer(row: Row[Any], assignments: Sequence[Row[Any]]) -> Lecturer:
    lecturer = Lecturer(row.lecturer_id, row.department_id, row.full_name)
    for assignment in assignments:
        lecturer.assign_to_course(assignment.course_id, assignment.session_id)
    return lecturer


def session_row(session: Session) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "start_year": session.academic_year.start_year,
        "status": session.status.value,
    }


def semester_rows(session: Session) -> list[dict[str, Any]]:
    return [
        {
            "semester_id": semester.semester_id,
            "session_id": session.session_id,
            "ordinal": semester.ordinal.value,
        }
        for semester in session.semesters
    ]


def to_session(row: Row[Any], semesters: Sequence[Row[Any]]) -> Session:
    return Session.restore(
        row.session_id,
        AcademicYear(row.start_year),
        [
            Semester(semester.semester_id, SemesterOrdinal(semester.ordinal))
            for semester in semesters
        ],
        SessionStatus(row.status),
    )


def children_of(children: Mapping[Table, Sequence[Row[Any]]], table: Table) -> Sequence[Row[Any]]:
    return children.get(table, ())


__all__ = [
    "assignment_rows",
    "children_of",
    "department_row",
    "faculty_row",
    "lecturer_row",
    "program_row",
    "semester_rows",
    "session_row",
    "to_department",
    "to_faculty",
    "to_lecturer",
    "to_program",
    "to_session",
]
