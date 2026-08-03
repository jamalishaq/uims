"""The ``AcademicRecord`` aggregate: everything one student has been graded on.

One record per student, holding every transcript line from every semester. Bigger than
the ``Enrollment`` aggregate next door, and deliberately so: a registration is a thing
that happens to one course, while a CGPA is by definition a statement about all of them
at once. An aggregate per graded course would put the university's headline number on a
query across rows and give nothing a place to enforce that a recorded grade stays put.

**Created by consuming ``GradeSubmitted``** (CLAUDE.md section 3) — grade submission is
the trigger, not semester close, so a record springs into existence the first time a
lecturer submits a mark for a student and nothing about a calendar has to fire.

**This context never queries Enrollment.** Nothing here asks whether the student was
registered for the course, what their credit load was, or whether the registration was
finalised. Faculty & Department has already established that the lecturer teaches the
course in an open session; a second opinion pulled from a third context would be this
aggregate re-deciding something that was decided upstream, over a dependency CLAUDE.md
forbids by name.

Immutability, which is this aggregate's central invariant, is enforced in three places at
once:

1. :class:`~academic_records.domain.transcript.CourseGrade` is frozen and derives its
   letter and grade point from the score, so a line cannot be edited or built inconsistent.
2. :meth:`AcademicRecord.record_grade` refuses to overwrite a line that already stands
   with a different score. Redelivery of the *same* grade is a no-op, because at-least-once
   delivery is normal on a bus and replaying a message must not be an error.
3. :meth:`AcademicRecord.correct_grade` is the only method that changes a recorded grade,
   and it demands a reason and an authorizer. There is no setter, no exposed list and no
   ``grades`` property that returns anything a caller can write into.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from academic_records.domain.errors import (
    GradeAlreadyRecordedError,
    GradeNotRecordedError,
    InvalidCorrectionError,
    MissingIdentifierError,
)
from academic_records.domain.grading_scale import LASU_GRADING_SCALE, GradingScale
from academic_records.domain.probation import ProbationPolicy, Standing
from academic_records.domain.transcript import CourseGrade, Transcript
from academic_records.domain.values import require_identifier, require_score, require_text


@dataclass(frozen=True)
class GradeCorrection:
    """The audit trail of one administrative correction.

    Kept because a corrected grade with no record of the correction is indistinguishable
    from a grade that was always that value, and the difference is the whole point of
    making corrections explicit. ``authorized_by`` is a name and not a role: this context
    has no user model and inventing one to hold a role would be a second identity system.
    """

    course_id: str
    semester_id: str
    previous_score: int
    corrected_score: int
    reason: str
    authorized_by: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "course_id", require_identifier(self.course_id, "course_id"))
        object.__setattr__(self, "semester_id", require_identifier(self.semester_id, "semester_id"))
        object.__setattr__(self, "previous_score", require_score(self.previous_score, "score"))
        object.__setattr__(self, "corrected_score", require_score(self.corrected_score, "score"))

    def __str__(self) -> str:
        return (
            f"{self.course_id} {self.semester_id}: {self.previous_score} -> "
            f"{self.corrected_score} by {self.authorized_by}"
        )


class AcademicRecord:
    """One student's grade history, its averages, and their standing."""

    def __init__(
        self,
        student_id: str,
        *,
        scale: GradingScale = LASU_GRADING_SCALE,
        probation: ProbationPolicy | None = None,
    ) -> None:
        if not isinstance(scale, GradingScale):
            raise TypeError("scale must be a GradingScale")
        self._student_id = require_identifier(student_id, "student_id")
        self._scale = scale
        self._probation = probation or ProbationPolicy()
        self._grades: list[CourseGrade] = []
        self._corrections: list[GradeCorrection] = []

    @classmethod
    def open(
        cls,
        student_id: str,
        *,
        scale: GradingScale = LASU_GRADING_SCALE,
        probation: ProbationPolicy | None = None,
    ) -> "AcademicRecord":
        """Start a record for a student who has just been graded for the first time.

        Named ``open`` rather than ``create`` because nothing opens one on purpose: the
        use case that consumes ``GradeSubmitted`` opens a record and records the grade in
        the same breath, so a stored record always has at least one line in it.
        """
        return cls(student_id, scale=scale, probation=probation)

    @classmethod
    def restore(
        cls,
        student_id: str,
        grades: Iterable[CourseGrade],
        corrections: Iterable[GradeCorrection] = (),
        *,
        scale: GradingScale = LASU_GRADING_SCALE,
        probation: ProbationPolicy | None = None,
    ) -> "AcademicRecord":
        """Rebuild a record from stored state. A persistence adapter is the only caller.

        **The lines are placed, not re-awarded.** Going back through :meth:`record_grade`
        would re-derive every letter and grade point from this record's *current* scale, and
        the whole reason ``grading_scale`` is held on the record is that "a student graded
        under one scale keeps the letters they were given if the university adopts another".
        A reconstitution that quietly re-graded a 2019 transcript under a 2027 scale would
        defeat the field it was reading. So the stored :class:`CourseGrade` values go in as
        they are — they are frozen, and they were validated when they were awarded.

        Replaying would also be wrong for a plainer reason: :meth:`record_grade` refuses a
        second score for a ``(course, semester)`` already held, so a record whose grade was
        later corrected could not be replayed at all. Its correction would raise.

        The corrections are the audit trail, and they are restored beside the lines rather
        than reapplied to them. Applying them would move each line to the end of the
        transcript, and "a correction fixes a mark rather than re-sitting a course".
        """
        record = cls(student_id, scale=scale, probation=probation)
        for grade in grades:
            if not isinstance(grade, CourseGrade):
                raise TypeError("a restored record is made of CourseGrade lines")
            record._grades.append(grade)
        for correction in corrections:
            if not isinstance(correction, GradeCorrection):
                raise TypeError("a restored record's corrections are GradeCorrection entries")
            record._corrections.append(correction)
        return record

    # ---- identity and configuration ----

    @property
    def student_id(self) -> str:
        return self._student_id

    @property
    def grading_scale(self) -> GradingScale:
        """The scale this record's grades were awarded on.

        Held on the record and not looked up at read time, so that a student graded under
        one scale keeps the letters they were given if the university adopts another. It
        is the same argument as the credit-units snapshot, one level up.
        """
        return self._scale

    @property
    def probation_policy(self) -> ProbationPolicy:
        return self._probation

    # ---- reading ----

    @property
    def grades(self) -> tuple[CourseGrade, ...]:
        """Every transcript line, in the order recorded. A tuple of frozen lines.

        There is no way in from here: the tuple is a copy, and mutating an element is not
        possible because ``CourseGrade`` is frozen. A caller that wants a grade changed has
        to go through :meth:`correct_grade`, which is the point.
        """
        return tuple(self._grades)

    @property
    def corrections(self) -> tuple[GradeCorrection, ...]:
        """Every administrative correction ever applied, oldest first."""
        return tuple(self._corrections)

    def transcript(self) -> Transcript:
        """A view over this record's lines, with the averages on it."""
        return Transcript(self._grades)

    @property
    def cgpa(self) -> Decimal:
        """The cumulative grade point average over every attempt, to two decimal places."""
        return self.transcript().cgpa

    @property
    def standing(self) -> Standing:
        """Whether this student is on probation, judged on the reported CGPA."""
        return self._probation.standing_for(self.cgpa)

    @property
    def passed_course_ids(self) -> frozenset[str]:
        """Every course passed on at least one attempt."""
        return self.transcript().passed_course_ids

    def semester_gpa(self, semester_id: str) -> Decimal:
        """The grade point average for one semester.

        Raises:
            GradeNotRecordedError: nothing was graded in that semester.
        """
        return self.transcript().semester_gpa(semester_id)

    def grade_for(self, course_id: str, semester_id: str) -> CourseGrade | None:
        """The line for one course in one semester, or ``None`` if there is none.

        ``None`` is an answer, not a failure: most courses a student has not sat.
        """
        key = (
            require_identifier(course_id, "course_id"),
            require_identifier(semester_id, "semester_id"),
        )
        return next((grade for grade in self._grades if grade.key == key), None)

    def has_grade_for(self, course_id: str, semester_id: str) -> bool:
        return self.grade_for(course_id, semester_id) is not None

    def _position_of(self, course_id: str, semester_id: str) -> int | None:
        """Where the line for this course and semester sits, so a correction can replace it there.

        By key rather than by value: a correction has to land on the line the record holds,
        and searching by equality would depend on ``CourseGrade``'s fields all matching.
        """
        key = (course_id, semester_id)
        return next((index for index, grade in enumerate(self._grades) if grade.key == key), None)

    # ---- writing ----

    def record_grade(
        self, *, course_id: str, semester_id: str, score: int, credit_units: int
    ) -> CourseGrade:
        """Record a submitted grade, and return the transcript line it became.

        Idempotent on redelivery. A bus that guarantees at-least-once delivery will replay
        ``GradeSubmitted``, and a replay that raised would turn ordinary transport
        behaviour into an incident; a replay carrying the same score for the same course in
        the same semester returns the line already held and changes nothing.

        A course sat again in a *different* semester is a different line, and both count
        towards the CGPA — the confirmed carry-over rule (CLAUDE.md section 6), which needs
        no code here because the key includes the semester.

        Raises:
            GradeAlreadyRecordedError: a *different* score already stands for this course in
                this semester. Recorded grades are final; :meth:`correct_grade` is the way
                through, and it asks for a reason.
            InvalidScoreError: the score is not a whole mark out of 100.
            InvalidCreditUnitsError: the credit units are not a whole, positive number.
            MissingIdentifierError: the course or semester id is blank.
        """
        course_id = require_identifier(course_id, "course_id")
        semester_id = require_identifier(semester_id, "semester_id")
        score = require_score(score)

        existing = self.grade_for(course_id, semester_id)
        if existing is not None:
            if existing.score == score:
                return existing
            raise GradeAlreadyRecordedError(
                f"student {self._student_id} already has {existing.score} recorded for "
                f"{course_id} in {semester_id}; a recorded grade is final and a change to "
                f"{score} must go through an administrative correction"
            )

        grade = CourseGrade.award(
            course_id=course_id,
            semester_id=semester_id,
            score=score,
            credit_units=credit_units,
            scale=self._scale,
        )
        self._grades.append(grade)
        return grade

    def correct_grade(
        self,
        *,
        course_id: str,
        semester_id: str,
        corrected_score: int,
        reason: str,
        authorized_by: str,
    ) -> GradeCorrection:
        """Change a recorded grade. The only method that can, and an explicit administrative act.

        The line is replaced in place — it keeps its position in the transcript, because a
        correction fixes a mark rather than re-sitting a course — and the change is appended
        to :attr:`corrections`. The new letter and grade point are re-derived from the
        corrected score on this record's own scale, so a correction cannot smuggle in a
        grade the scale does not award. Credit units are carried over from the line being
        corrected: what is being fixed is the mark, and re-reading the course's worth would
        let a correction quietly re-weight a semester nobody meant to touch.

        Raises:
            GradeNotRecordedError: no grade stands for this course in this semester. A
                correction is a change to something, and there is nothing here to change.
            InvalidCorrectionError: the reason or the authorizer is blank, or the corrected
                score is the one already recorded. A correction that changes nothing would
                leave an audit entry describing an event that did not happen.
        """
        course_id = require_identifier(course_id, "course_id")
        semester_id = require_identifier(semester_id, "semester_id")
        corrected_score = require_score(corrected_score, "corrected score")

        position = self._position_of(course_id, semester_id)
        if position is None:
            raise GradeNotRecordedError(
                f"student {self._student_id} has no grade recorded for {course_id} in "
                f"{semester_id}; there is nothing to correct"
            )
        existing = self._grades[position]

        try:
            reason = require_text(reason, "reason")
            authorized_by = require_text(authorized_by, "authorized_by")
        except MissingIdentifierError as blank:
            raise InvalidCorrectionError(
                "a grade correction must state a reason and who authorized it"
            ) from blank

        if existing.score == corrected_score:
            raise InvalidCorrectionError(
                f"{course_id} in {semester_id} is already recorded as {corrected_score}; "
                "a correction that changes nothing is not a correction"
            )

        corrected = CourseGrade.award(
            course_id=course_id,
            semester_id=semester_id,
            score=corrected_score,
            credit_units=existing.credit_units,
            scale=self._scale,
        )
        self._grades[position] = corrected
        correction = GradeCorrection(
            course_id=course_id,
            semester_id=semester_id,
            previous_score=existing.score,
            corrected_score=corrected_score,
            reason=reason,
            authorized_by=authorized_by,
        )
        self._corrections.append(correction)
        return correction

    def __repr__(self) -> str:
        return (
            f"AcademicRecord(student_id={self._student_id!r}, "
            f"grades={len(self._grades)}, cgpa={self.cgpa}, standing={self.standing.name})"
        )
