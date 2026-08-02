"""Inbound adapter: Admissions has matriculated an applicant, so a student now exists.

The second of the two creation paths, and the reason both are worth spelling out
together: this handler *translates*, it does not decide. It turns Admissions' fact into
a ``RegisterNewStudentCommand`` and calls the same use case an administrator calls, so
the matric number a matriculated student gets is composed by the same issuer, from the
same sequence, in the same format as one registered by hand.

:class:`StudentMatriculatedMessage` is this context's own reading of the event, not
Admissions' class. A consumer never imports a publisher's event type (CLAUDE.md section
3) — Admissions is free to add fields to what it publishes without this file caring, and
the fitness test would reject the import anyway. Phase 3 wires the real event: a bus
adapter deserialises whatever crosses the wire into this message and calls
:meth:`StudentMatriculatedHandler.handle`.

Note what is *not* here. Nothing is published back. A matric number is not needed at
acceptance-letter time, so Admissions is never told what was issued (CLAUDE.md section 3).

``student_id`` is minted here rather than carried on the event because it is this
context's identifier: Admissions has no business naming our aggregate. It has no relation
to the matric number, which is issued inside the use case and cannot be known yet.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from uuid import uuid4

from student_profile.application.register_new_student import (
    DEFAULT_ENTRY_LEVEL,
    RegisterNewStudent,
    RegisterNewStudentCommand,
)
from student_profile.domain.student import Student
from student_profile.ports.student_repository import StudentRepositoryPort


@dataclass(frozen=True)
class StudentMatriculatedMessage:
    """What this context takes from Admissions' ``StudentMatriculated``.

    ``program_id`` is the *offered* program, which is not always the one applied for.
    There is no matric number in the payload — issuing it is this context's job, and an
    event that carried one would mean Admissions had already done it.

    ``entry_level`` defaults rather than being required: an entry level is not something
    Admissions has an opinion about, and a bus adapter that has nothing to fill it with
    should not have to invent a value.
    """

    applicant_id: str
    program_id: str
    session_id: str
    full_name: str
    date_of_birth: date | None = None
    email: str | None = None
    phone_number: str | None = None
    entry_level: int = DEFAULT_ENTRY_LEVEL


class StudentMatriculatedHandler:
    """Creates the student a matriculated applicant became."""

    def __init__(
        self,
        register_new_student: RegisterNewStudent,
        students: StudentRepositoryPort,
        new_student_id: Callable[[], str] | None = None,
    ) -> None:
        self._register_new_student = register_new_student
        self._students = students
        self._new_student_id = new_student_id or (lambda: uuid4().hex)

    def handle(self, message: StudentMatriculatedMessage) -> Student:
        """Register the student, or return the one this applicant already became.

        Redelivery is normal, not exceptional: a bus that guarantees at-least-once
        delivery will replay this event, and issuing a second matric number to somebody
        who already holds one is the failure that would cause. So the applicant is looked
        up first, and a repeat delivery is a no-op that returns the existing student.

        The check is not a substitute for the unique constraint Phase 6 puts on
        ``applicant_id``: two deliveries handled at the same instant can both find
        nothing. It turns the ordinary case into a no-op; the constraint catches the race.
        """
        existing = self._students.find_by_applicant(message.applicant_id)
        if existing is not None:
            return existing

        command = RegisterNewStudentCommand(
            student_id=self._new_student_id(),
            program_id=message.program_id,
            entry_session_id=message.session_id,
            full_name=message.full_name,
            date_of_birth=message.date_of_birth,
            email=message.email,
            phone_number=message.phone_number,
            entry_level=message.entry_level,
            applicant_id=message.applicant_id,
        )
        return self._register_new_student.execute(command)
