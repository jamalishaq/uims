"""Read a student's record: the transcript, the averages, and the standing.

This is the surface the rest of the university reads Academic Records through, and in
particular it is what the adapter behind Enrollment's ``StudentAcademicStandingPort`` will
call when Phase 6 replaces its hand-fed stub. That adapter's docstring already names the
two translations it will perform — grades to passes, probation to standing — and both are
done *here*, on this side of the boundary, which is why :class:`StudentRecordView` carries
``passed_course_ids`` and a :class:`~academic_records.domain.probation.Standing` rather
than a list of letters and a number.

The view is a DTO and not the aggregate. Handing out an ``AcademicRecord`` would hand out
``record_grade`` and ``correct_grade`` along with it, and a read path that can write is a
read path somebody will eventually write through.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from academic_records.application.errors import AcademicRecordNotFoundError
from academic_records.domain.academic_record import GradeCorrection
from academic_records.domain.probation import Standing
from academic_records.domain.transcript import CourseGrade
from academic_records.ports.academic_record_repository import AcademicRecordRepositoryPort


@dataclass(frozen=True)
class StudentRecordView:
    """Everything a reader can be told about a student's record, and nothing they can change.

    ``semester_gpas`` is keyed by semester id in order of first appearance, which is the
    only ordering this context can honestly offer: ``GradeSubmitted`` carries no session
    and the semester id is Faculty & Department's opaque key (see
    ``academic_records.domain.transcript``).
    """

    student_id: str
    cgpa: Decimal
    standing: Standing
    total_units: int
    grades: tuple[CourseGrade, ...]
    semester_gpas: Mapping[str, Decimal]
    passed_course_ids: frozenset[str]
    corrections: tuple[GradeCorrection, ...]


class ReadAcademicRecord:
    """Answers questions about a student's record without letting anybody change one."""

    def __init__(self, records: AcademicRecordRepositoryPort) -> None:
        self._records = records

    async def execute(self, student_id: str) -> StudentRecordView:
        """Return the student's record.

        Raises:
            AcademicRecordNotFoundError: nobody has graded this student yet.
        """
        view = await self.find(student_id)
        if view is None:
            raise AcademicRecordNotFoundError(
                f"no academic record is stored for student {student_id!r}"
            )
        return view

    async def find(self, student_id: str) -> StudentRecordView | None:
        """Return the student's record, or ``None`` if nobody has graded them yet.

        The form a *port adapter* wants, and the reason both exist. Enrollment's
        ``StudentAcademicStandingPort`` documents ``None`` as meaning "no record", which it
        reads as a fresher rather than a refusal — an exception would make the first
        registration of every student's life run through an error handler.
        """
        record = await self._records.get(student_id)
        if record is None:
            return None

        transcript = record.transcript()
        return StudentRecordView(
            student_id=record.student_id,
            cgpa=record.cgpa,
            standing=record.standing,
            total_units=transcript.total_units,
            grades=transcript.grades,
            semester_gpas=transcript.semester_gpas(),
            passed_course_ids=transcript.passed_course_ids,
            corrections=record.corrections,
        )
