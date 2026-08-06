"""Inbound adapter: Admissions has matriculated an applicant, so a student now exists.

The second of the two creation paths, and the reason both are worth spelling out
together: this handler *translates*, it does not decide. It turns Admissions' fact into
a ``RegisterNewStudentCommand`` and calls the same use case an administrator calls, so
the matric number a matriculated student gets is composed by the same issuer, from the
same sequence, in the same format as one registered by hand.

:class:`StudentMatriculatedMessage` is this context's own reading of the event, not
Admissions' class. A consumer never imports a publisher's event type (CLAUDE.md section
3) — Admissions is free to add fields to what it publishes without this file caring, and
the fitness test would reject the import anyway. The deserialising half arrived with the
publisher: Admissions now has an ``EventPublisherPort`` and a ``MatriculateApplicant`` use
case behind it, so :meth:`StudentMatriculatedMessage.from_payload` reads keys off a real
contract rather than guessing them.

``bio_data`` arrives as a nested mapping rather than four top-level fields, because it is a
value object over in Admissions and :func:`dataclasses.asdict` preserves the nesting. Taking
it apart here is exactly the anti-corruption translation this file exists to do — the shape
Admissions holds a person in is not the shape this context registers one in.

Note what is *not* here. Nothing is published back. A matric number is not needed at
acceptance-letter time, so Admissions is never told what was issued (CLAUDE.md section 3).

``student_id`` is minted here rather than carried on the event because it is this
context's identifier: Admissions has no business naming our aggregate. It has no relation
to the matric number, which is issued inside the use case and cannot be known yet.
"""

from collections.abc import Callable, Mapping
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

STUDENT_MATRICULATED = "StudentMatriculated"
"""The name this context subscribes under. A string, because the bus carries no classes."""


def _optional_text(value: object) -> str | None:
    """An optional string field off the wire, absent and blank alike reading as absent."""
    return None if value is None else str(value)


def _optional_date(value: object) -> date | None:
    """A date off the wire, however the transport chose to carry one.

    The in-memory bus hands over whatever ``dataclasses.asdict`` produced, which leaves a
    ``date`` a ``date``. A broker that serialises to JSON would send its ISO form instead,
    and a consumer that only understood one of the two would be a consumer that breaks on
    the day the transport is replaced.
    """
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


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

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "StudentMatriculatedMessage":
        """Build the message from what the bus delivered, flattening the bio-data.

        ``full_name`` is required and a missing one is a ``KeyError``: a student registered
        under an empty name is worse than a delivery that failed loudly, and the matric
        number issued alongside it would be permanent. The three optional fields use ``get``
        because Admissions genuinely may not hold them — its ``BioData`` requires only a name,
        "because a record that cannot be created without a phone number is a record that will
        be created with a fake one".

        ``entry_level`` is not read at all. No key for it exists on the wire, because
        Admissions has no opinion about a level, and this context's ``DEFAULT_ENTRY_LEVEL``
        is the answer.
        """
        bio_data = payload["bio_data"]
        if not isinstance(bio_data, Mapping):
            raise TypeError(
                f"StudentMatriculated carries bio_data as a mapping; got {type(bio_data).__name__}"
            )
        return cls(
            applicant_id=str(payload["applicant_id"]),
            program_id=str(payload["program_id"]),
            session_id=str(payload["session_id"]),
            full_name=str(bio_data["full_name"]),
            date_of_birth=_optional_date(bio_data.get("date_of_birth")),
            email=_optional_text(bio_data.get("email")),
            phone_number=_optional_text(bio_data.get("phone_number")),
        )


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

    async def handle(self, message: StudentMatriculatedMessage) -> Student:
        """Register the student, or return the one this applicant already became.

        Redelivery is normal, not exceptional: a bus that guarantees at-least-once
        delivery will replay this event, and issuing a second matric number to somebody
        who already holds one is the failure that would cause. So the applicant is looked
        up first, and a repeat delivery is a no-op that returns the existing student.

        The check is not a substitute for the unique constraint Phase 6 puts on
        ``applicant_id``: two deliveries handled at the same instant can both find
        nothing. It turns the ordinary case into a no-op; the constraint catches the race.
        """
        existing = await self._students.find_by_applicant(message.applicant_id)
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
        return await self._register_new_student.execute(command)

    async def on_message(self, payload: Mapping[str, object]) -> None:
        """Subscribe *this* to a bus: deserialise, then handle.

        The signature a transport can call without knowing anything about this context —
        which is what lets the wiring that connects Admissions to Student Profile be a single
        line in a composition root, importing neither context's event type.
        """
        await self.handle(StudentMatriculatedMessage.from_payload(payload))
