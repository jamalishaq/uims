"""The one repository this context declares, against Postgres.

Short, because the aggregate is the only thing here and the ports layer says why: no publisher,
no port into Enrollment, and one query outward that is not a repository. What this file has to
get right is that a transcript comes back exactly as it was written — the same lines, in the
same order, carrying the same letters.
"""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import Row, Table
from sqlalchemy.ext.asyncio import AsyncEngine

from academic_records.adapters.outbound.postgres import _tables as t
from academic_records.adapters.outbound.postgres._repository import PostgresRepository
from academic_records.domain.academic_record import AcademicRecord, GradeCorrection
from academic_records.domain.transcript import CourseGrade
from academic_records.ports.academic_record_repository import AcademicRecordRepositoryPort


class PostgresAcademicRecordRepository(
    PostgresRepository[AcademicRecord], AcademicRecordRepositoryPort
):
    """Holds academic records in Postgres, keyed by the student they belong to."""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(
            engine, label="academic record", table=t.academic_records, key=("student_id",)
        )

    @property
    def child_tables(self) -> Sequence[tuple[Table, Sequence[str]]]:
        return (
            (t.course_grades, ("student_id",)),
            (t.grade_corrections, ("student_id",)),
        )

    def identity_of(self, aggregate: AcademicRecord) -> tuple[str]:
        return (aggregate.student_id,)

    def row_of(self, aggregate: AcademicRecord) -> dict[str, Any]:
        return {"student_id": aggregate.student_id}

    def child_rows_of(self, aggregate: AcademicRecord) -> Mapping[Table, Sequence[dict[str, Any]]]:
        return {
            t.course_grades: [
                {
                    "student_id": aggregate.student_id,
                    "course_id": grade.course_id,
                    "semester_id": grade.semester_id,
                    "position": position,
                    "score": grade.score,
                    "credit_units": grade.credit_units,
                    "letter": grade.letter,
                    "grade_point": grade.grade_point,
                }
                for position, grade in enumerate(aggregate.grades)
            ],
            t.grade_corrections: [
                {
                    "student_id": aggregate.student_id,
                    "position": position,
                    "course_id": correction.course_id,
                    "semester_id": correction.semester_id,
                    "previous_score": correction.previous_score,
                    "corrected_score": correction.corrected_score,
                    "reason": correction.reason,
                    "authorized_by": correction.authorized_by,
                }
                for position, correction in enumerate(aggregate.corrections)
            ],
        }

    def restore(
        self, row: Row[Any], children: Mapping[Table, Sequence[Row[Any]]]
    ) -> AcademicRecord:
        """Lines in the order they were recorded, letters as they were awarded.

        ``position`` is what "in the order recorded" means once rows are involved, and the
        order is not decorative: ``Transcript.semester_ids`` reports semesters "in order of
        first appearance", because ``GradeSubmitted`` carries no calendar and inventing one
        here would be this context owning something it does not.
        """
        grades = sorted(children.get(t.course_grades, ()), key=lambda child: child.position)
        corrections = sorted(
            children.get(t.grade_corrections, ()), key=lambda child: child.position
        )
        return AcademicRecord.restore(
            row.student_id,
            [
                CourseGrade(
                    course_id=grade.course_id,
                    semester_id=grade.semester_id,
                    score=grade.score,
                    credit_units=grade.credit_units,
                    letter=grade.letter,
                    grade_point=Decimal(grade.grade_point),
                )
                for grade in grades
            ],
            [
                GradeCorrection(
                    course_id=correction.course_id,
                    semester_id=correction.semester_id,
                    previous_score=correction.previous_score,
                    corrected_score=correction.corrected_score,
                    reason=correction.reason,
                    authorized_by=correction.authorized_by,
                )
                for correction in corrections
            ],
        )

    async def add(self, record: AcademicRecord) -> None:
        await self._add(record)

    async def save(self, record: AcademicRecord) -> None:
        await self._save(record)

    async def get(self, student_id: str) -> AcademicRecord | None:
        return await self._get(student_id)
