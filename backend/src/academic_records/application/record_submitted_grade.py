"""Record a grade that a lecturer has submitted, opening the student's record if it is their first.

Orchestration only. Whether the lecturer was entitled to submit the mark was settled in
Faculty & Department before the event was published, and what the mark is worth is
:class:`~academic_records.domain.grading_scale.GradingScale`'s to say. This use case
fetches, hands over, and stores.

Two aggregate-free decisions live here and nowhere else:

* **Open on first grade.** A missing record is not an error, it is a fresher. CLAUDE.md
  section 3 says the record is "created by consuming ``GradeSubmitted`` — grade submission
  is the trigger, not semester close", and this is that sentence in code.
* **A course of unknown worth is refused.** The port answering ``None`` becomes
  :class:`CourseCreditsUnavailableError` rather than a default unit count.

**No transaction spans two aggregates** (CLAUDE.md section 4) — there is only one here, and
one write. The grade is recorded on the aggregate and then the aggregate is stored; a crash
between the two loses the grade, which redelivery replays.
"""

from dataclasses import dataclass

from academic_records.application.errors import CourseCreditsUnavailableError
from academic_records.domain.academic_record import AcademicRecord
from academic_records.domain.transcript import CourseGrade
from academic_records.ports.academic_record_repository import AcademicRecordRepositoryPort
from academic_records.ports.course_credit import CourseCreditPort


@dataclass(frozen=True)
class RecordSubmittedGradeCommand:
    """One submitted mark, in primitives.

    The four fields of ``GradeSubmitted`` and nothing else — in particular no credit units.
    A caller that could state what the course was worth could state it wrongly, and every
    CGPA computed from that line would be wrong with no way to tell. It is looked up.
    """

    student_id: str
    course_id: str
    semester_id: str
    score: int


@dataclass(frozen=True)
class GradeRecorded:
    """The transcript line the submission became, and whether it is new.

    ``was_already_recorded`` is how a caller tells a first delivery from a replay without
    comparing states itself. Both are successes: an at-least-once bus replays, and a replay
    that looked like a failure would have somebody investigating normal transport
    behaviour.
    """

    student_id: str
    grade: CourseGrade
    was_already_recorded: bool


class RecordSubmittedGrade:
    """Turn a submitted mark into a line on a student's academic record."""

    def __init__(
        self,
        records: AcademicRecordRepositoryPort,
        courses: CourseCreditPort,
    ) -> None:
        self._records = records
        self._courses = courses

    def execute(self, command: RecordSubmittedGradeCommand) -> GradeRecorded:
        """Record the grade, opening the student's record if this is their first.

        Raises:
            CourseCreditsUnavailableError: Course Catalog does not know the course, so
                there is no weight to record the line at.
            GradeAlreadyRecordedError: a *different* mark already stands for this course in
                this semester. Recorded grades are final; ``CorrectGrade`` is the way
                through.
            AcademicRecordsError: the score or an identifier is invalid. Domain errors pass
                through untranslated — the domain already says exactly what went wrong.
        """
        credits = self._courses.credits_for(command.course_id)
        if credits is None:
            raise CourseCreditsUnavailableError(
                f"the catalog does not know course {command.course_id!r}, so the grade "
                f"submitted for student {command.student_id!r} has no credit weight and "
                "cannot be recorded"
            )

        record = self._records.get(command.student_id)
        is_new_record = record is None
        if record is None:
            record = AcademicRecord.open(command.student_id)

        already_recorded = record.has_grade_for(command.course_id, command.semester_id)
        grade = record.record_grade(
            course_id=command.course_id,
            semester_id=command.semester_id,
            score=command.score,
            credit_units=credits.credit_units,
        )

        if is_new_record:
            self._records.add(record)
        elif not already_recorded:
            self._records.save(record)

        return GradeRecorded(
            student_id=record.student_id,
            grade=grade,
            was_already_recorded=already_recorded,
        )
