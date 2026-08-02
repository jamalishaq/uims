"""The ``Course`` aggregate: one entry in the catalog.

A course is a description, not an event and not an enrolment. It knows its code, its
title, what it is worth, which department offers it, and which courses come before it.
It has no notion of a specific student (CLAUDE.md section 3) — no capacity, no
register, no semester. Those belong to Enrollment, which will read this catalog through
its own ``CourseInfoPort`` and never the other way round.

``department_id`` is Faculty & Department's identifier, opaque to us. Prerequisite ids
are our own, but the aggregate still treats them as opaque strings: a course holds the
ids of the courses that come before it and nothing more. Reading a chain means walking
several aggregates, which is :class:`PrerequisiteGraph`'s job, not this class's.

Courses are retired rather than deleted. Enrollment and Academic Records hold
``course_id``s indefinitely — a transcript from 2019 refers to courses no longer
taught — so an id that once resolved must keep resolving.
"""

from collections.abc import Iterable

from course_catalog.domain.errors import (
    DuplicatePrerequisiteError,
    PrerequisiteNotRequiredError,
    SelfPrerequisiteError,
)
from course_catalog.domain.values import (
    require_code,
    require_credit_units,
    require_identifier,
    require_text,
)


class Course:
    """A course of instruction, e.g. CSC101 Introduction to Computer Science."""

    def __init__(
        self,
        course_id: str,
        department_id: str,
        code: str,
        title: str,
        credit_units: int,
        *,
        prerequisite_ids: Iterable[str] = (),
        active: bool = True,
    ) -> None:
        self._course_id = require_identifier(course_id, "course_id")
        self._department_id = require_identifier(department_id, "department_id")
        self._code = require_code(code, "course code")
        self._title = require_text(title, "course title")
        self._credit_units = require_credit_units(credit_units, "credit units")
        self._active = bool(active)
        self._prerequisite_ids: list[str] = []
        for prerequisite_id in prerequisite_ids:
            self.add_prerequisite(prerequisite_id)

    @classmethod
    def create(
        cls,
        course_id: str,
        department_id: str,
        code: str,
        title: str,
        credit_units: int,
    ) -> "Course":
        """A new course is active and requires nothing until someone says otherwise."""
        return cls(course_id, department_id, code, title, credit_units)

    @property
    def course_id(self) -> str:
        return self._course_id

    @property
    def department_id(self) -> str:
        return self._department_id

    @property
    def code(self) -> str:
        return self._code

    @property
    def title(self) -> str:
        return self._title

    @property
    def credit_units(self) -> int:
        return self._credit_units

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def prerequisite_ids(self) -> tuple[str, ...]:
        """The courses required before this one, in the order they were added.

        A copy: callers cannot reach in and rewrite the catalog's prerequisites.
        """
        return tuple(self._prerequisite_ids)

    def add_prerequisite(self, prerequisite_id: str) -> None:
        """Require another course before this one.

        A course cannot require itself. That check lives here rather than in a use case
        because it needs nothing but the aggregate — no amount of repository lookup
        makes CSC101-requires-CSC101 sensible. A *longer* loop is a different problem,
        because seeing it means reading courses this one has never heard of; that check
        belongs to :class:`PrerequisiteGraph`.

        Raises:
            SelfPrerequisiteError: the prerequisite is this course.
            DuplicatePrerequisiteError: this course already requires it.
            MissingIdentifierError: the prerequisite id was blank.
        """
        prerequisite_id = require_identifier(prerequisite_id, "prerequisite_id")
        if prerequisite_id == self._course_id:
            raise SelfPrerequisiteError(f"course {self._course_id} cannot require itself")
        if prerequisite_id in self._prerequisite_ids:
            raise DuplicatePrerequisiteError(
                f"course {self._course_id} already requires {prerequisite_id}"
            )
        self._prerequisite_ids.append(prerequisite_id)

    def remove_prerequisite(self, prerequisite_id: str) -> None:
        """Stop requiring another course.

        Raises:
            PrerequisiteNotRequiredError: this course does not require it.
        """
        prerequisite_id = require_identifier(prerequisite_id, "prerequisite_id")
        if prerequisite_id not in self._prerequisite_ids:
            raise PrerequisiteNotRequiredError(
                f"course {self._course_id} does not require {prerequisite_id}"
            )
        self._prerequisite_ids.remove(prerequisite_id)

    def requires(self, prerequisite_id: str) -> bool:
        """Whether this course *directly* requires the given one."""
        return prerequisite_id in self._prerequisite_ids

    def retitle(self, title: str) -> None:
        self._title = require_text(title, "course title")

    def set_credit_units(self, credit_units: int) -> None:
        self._credit_units = require_credit_units(credit_units, "credit units")

    def transfer_to_department(self, department_id: str) -> None:
        """Move the course to another offering department."""
        self._department_id = require_identifier(department_id, "department_id")

    def retire(self) -> None:
        """Withdraw the course from the catalog without forgetting it ever existed."""
        self._active = False

    def reinstate(self) -> None:
        self._active = True

    def __repr__(self) -> str:
        return (
            f"Course(course_id={self._course_id!r}, code={self._code!r}, "
            f"credit_units={self._credit_units}, active={self._active})"
        )
