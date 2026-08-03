"""Enrollment's two repository ports, against Postgres.

The two reads worth looking at are ``list_for_student_in_term`` and ``has_registered_before``,
and the port has an opinion about both. The first is deliberately one query answering two
questions — the credit load and the duplicate check — because "two methods would be two round
trips answering from two reads of the same rows, and a moment where the load and the duplicate
check could disagree". The second is deliberately narrow: a boolean, not a history, so callers
cannot re-derive rules from it.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import Row, Table, and_
from sqlalchemy.ext.asyncio import AsyncEngine

from enrollment.adapters.outbound.postgres import _tables as t
from enrollment.adapters.outbound.postgres._repository import PostgresRepository
from enrollment.domain.course_offering import CourseOffering
from enrollment.domain.enrollment import Enrollment, EnrollmentStatus
from enrollment.domain.values import SemesterOrdinal, Term
from enrollment.ports.course_offering_repository import CourseOfferingRepositoryPort
from enrollment.ports.enrollment_repository import EnrollmentRepositoryPort


def _term_columns(table: Table, term: Term) -> Any:
    """``Term`` as a where clause. Three columns, because it is stored as three."""
    return and_(
        table.c.session_id == term.session_id,
        table.c.semester_id == term.semester_id,
    )


def _to_term(row: Row[Any]) -> Term:
    return Term(
        session_id=row.session_id,
        semester_id=row.semester_id,
        ordinal=SemesterOrdinal(row.term_ordinal),
    )


class PostgresEnrollmentRepository(PostgresRepository[Enrollment], EnrollmentRepositoryPort):
    """Holds registrations in Postgres."""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(engine, label="enrollment", table=t.enrollments, key=("enrollment_id",))

    def identity_of(self, aggregate: Enrollment) -> tuple[str]:
        return (aggregate.enrollment_id,)

    def row_of(self, aggregate: Enrollment) -> dict[str, Any]:
        return {
            "enrollment_id": aggregate.enrollment_id,
            "student_id": aggregate.student_id,
            "course_id": aggregate.course_id,
            "session_id": aggregate.term.session_id,
            "semester_id": aggregate.term.semester_id,
            "term_ordinal": aggregate.term.ordinal.value,
            "credit_units": aggregate.credit_units,
            "is_carry_over": aggregate.is_carry_over,
            "status": aggregate.status.value,
        }

    def restore(self, row: Row[Any], children: Mapping[Table, Sequence[Row[Any]]]) -> Enrollment:
        return Enrollment.restore(
            row.enrollment_id,
            row.student_id,
            row.course_id,
            _to_term(row),
            row.credit_units,
            is_carry_over=row.is_carry_over,
            status=EnrollmentStatus(row.status),
        )

    async def add(self, enrollment: Enrollment) -> None:
        await self._add(enrollment)

    async def save(self, enrollment: Enrollment) -> None:
        await self._save(enrollment)

    async def get(self, enrollment_id: str) -> Enrollment | None:
        return await self._get(enrollment_id)

    async def list_for_student_in_term(self, student_id: str, term: Term) -> tuple[Enrollment, ...]:
        return await self._list(
            and_(t.enrollments.c.student_id == student_id, _term_columns(t.enrollments, term))
        )

    async def has_registered_before(self, student_id: str, course_id: str) -> bool:
        """A boolean off an index, and nothing wider.

        ``EXISTS`` rather than loading the registrations and counting them, because the port is
        pointed about what this answers: "nothing about *when* or *how many times* enters any
        decision Enrollment makes today". A method that read the rows would invite one.
        """
        return await self._exists(
            and_(
                t.enrollments.c.student_id == student_id,
                t.enrollments.c.course_id == course_id,
            )
        )


class PostgresCourseOfferingRepository(
    PostgresRepository[CourseOffering], CourseOfferingRepositoryPort
):
    """Holds offerings in Postgres, keyed by the course and the term it is run in."""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(
            engine,
            label="course offering",
            table=t.course_offerings,
            key=("course_id", "session_id", "semester_id"),
        )

    def identity_of(self, aggregate: CourseOffering) -> tuple[str, str, str]:
        return (aggregate.course_id, aggregate.term.session_id, aggregate.term.semester_id)

    def row_of(self, aggregate: CourseOffering) -> dict[str, Any]:
        return {
            "course_id": aggregate.course_id,
            "session_id": aggregate.term.session_id,
            "semester_id": aggregate.term.semester_id,
            "term_ordinal": aggregate.term.ordinal.value,
            "capacity": aggregate.capacity,
            "seats_taken": aggregate.seats_taken,
        }

    def restore(
        self, row: Row[Any], children: Mapping[Table, Sequence[Row[Any]]]
    ) -> CourseOffering:
        return CourseOffering(
            row.course_id, _to_term(row), row.capacity, seats_taken=row.seats_taken
        )

    async def add(self, offering: CourseOffering) -> None:
        await self._add(offering)

    async def save(self, offering: CourseOffering) -> None:
        await self._save(offering)

    async def get(self, course_id: str, term: Term) -> CourseOffering | None:
        return await self._get(course_id, term.session_id, term.semester_id)
