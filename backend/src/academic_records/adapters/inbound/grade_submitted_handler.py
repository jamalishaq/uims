"""Inbound adapter: a lecturer has submitted a grade, so a transcript line exists.

The trigger for this whole context. CLAUDE.md section 3: the ``AcademicRecord`` is
"created by consuming ``GradeSubmitted`` — grade submission is the trigger, not semester
close", and this handler is where that consumption happens.

It *translates*, it does not decide. Whether the lecturer teaches the course, whether the
session is open, whether the semester belongs to it — all settled in Faculty & Department
before the event was published, and none of it re-checked here. What the mark is worth and
whether it may be recorded belong to the domain on this side. This file turns a payload
into a command.

:class:`GradeSubmittedMessage` is **this context's own reading of the event**, not Faculty
& Department's class. A consumer never imports a publisher's event type (CLAUDE.md section
3): the publisher is free to add fields without this file caring, and the architecture
fitness test would reject the import anyway. The same arrangement Student Profile already
uses for ``StudentMatriculated``.

What crosses the bus is plain data — a name and a mapping — and :meth:`from_payload` is
where it becomes a typed thing again. That is the deserialising half of what
``faculty_department.domain.events`` promises when it says "an outbound adapter serialises
them at the boundary".
"""

from collections.abc import Mapping
from dataclasses import dataclass

from academic_records.application.record_submitted_grade import (
    GradeRecorded,
    RecordSubmittedGrade,
    RecordSubmittedGradeCommand,
)

GRADE_SUBMITTED = "GradeSubmitted"
"""The name this context subscribes under. A string, because the bus carries no classes."""


@dataclass(frozen=True)
class GradeSubmittedMessage:
    """What this context takes from Faculty & Department's ``GradeSubmitted``.

    All four fields the event carries, and no more. Notably absent is anything about a
    session: the event has none, and inventing one by parsing ``semester_id`` would be this
    context making up a calendar Faculty & Department owns.

    ``score`` rather than ``grade``. Over there the field is named for what a lecturer
    submits; here the same number is the input to a grading scale, and calling it a grade
    before it has met one would make the two words mean the same thing in a context whose
    whole job is that they do not.
    """

    student_id: str
    course_id: str
    semester_id: str
    score: int

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "GradeSubmittedMessage":
        """Build the message from what the bus delivered.

        Fields are read by name and the rest of the payload is ignored, so a publisher
        adding a field does not break this consumer. A *missing* field is a ``KeyError``
        and stays one: it means the contract this context was written against is not what
        arrived, and a message quietly defaulted into shape would record somebody's mark
        against the wrong course.
        """
        return cls(
            student_id=str(payload["student_id"]),
            course_id=str(payload["course_id"]),
            semester_id=str(payload["semester_id"]),
            score=int(payload["grade"]),  # type: ignore[call-overload]
        )


class GradeSubmittedHandler:
    """Records the grade a lecturer submitted."""

    def __init__(self, record_submitted_grade: RecordSubmittedGrade) -> None:
        self._record_submitted_grade = record_submitted_grade

    def handle(self, message: GradeSubmittedMessage) -> GradeRecorded:
        """Record the grade, opening the student's record if this is their first.

        Redelivery is normal, not exceptional: a bus that guarantees at-least-once delivery
        will replay this event. A replay carrying the same mark is a no-op — the idempotency
        lives on the aggregate, where it is an invariant rather than a handler's good
        manners, and the result says ``was_already_recorded`` so a caller can tell.
        """
        return self._record_submitted_grade.execute(
            RecordSubmittedGradeCommand(
                student_id=message.student_id,
                course_id=message.course_id,
                semester_id=message.semester_id,
                score=message.score,
            )
        )

    def on_message(self, payload: Mapping[str, object]) -> None:
        """Subscribe *this* to a bus: deserialise, then handle.

        The signature a transport can call without knowing anything about this context —
        which is what lets the wiring that connects the two be a single line in a
        composition root, importing neither context's event type.
        """
        self.handle(GradeSubmittedMessage.from_payload(payload))
