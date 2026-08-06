"""The academic calendar: planning a session, and opening it.

Two use cases, and the second one matters more than its size suggests. ``Session.open()``
produces ``SessionOpened``, which Billing consumes to batch-apply the session's fee schedule to
every active account. That subscription has been wired since Phase 4 and **nothing has ever
published the event**, because no use case called ``open()``. This is the publisher.

So opening a session is not a status flip: it bills a cohort. The event goes out through the
same ``EventPublisherPort`` ``SubmitGrade`` uses, and this use case cannot name its audience —
Billing is introduced to it by a composition root that imports both.

Planning and opening are deliberately separate. A session is described months before it starts,
and describing it must not charge anybody; the aggregate enforces the same split by refusing to
re-open a session that is already open.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from faculty_department.application.errors import SessionNotFoundError
from faculty_department.domain.session import Semester, SemesterOrdinal, Session
from faculty_department.domain.values import AcademicYear
from faculty_department.ports.event_publisher import EventPublisherPort
from faculty_department.ports.session_repository import SessionRepositoryPort


@dataclass(frozen=True)
class PlannedSemester:
    """One semester of a planned session, in primitives.

    ``ordinal`` is the enum's value — ``1`` for first, ``2`` for second — rather than the enum
    itself, because a command is what crosses from a transport and a transport does not hold
    this context's types. Turning it back into a ``SemesterOrdinal`` is this use case's job,
    and an unrecognised value raises there rather than becoming a semester nobody can order.
    """

    semester_id: str
    ordinal: int


@dataclass(frozen=True)
class PlanSessionCommand:
    """An academic session and the semesters that subdivide it.

    ``academic_year`` is the starting year as an integer — 2026 for the 2026/2027 session.
    ``AcademicYear`` derives the label from it, so the two can never disagree.
    """

    session_id: str
    academic_year: int
    semesters: tuple[PlannedSemester, ...]


@dataclass(frozen=True)
class OpenSessionCommand:
    """Open a planned session. This is what bills the cohort."""

    session_id: str


class PlanSession:
    """Describe a session before it starts. Nothing is charged."""

    def __init__(self, sessions: SessionRepositoryPort) -> None:
        self._sessions = sessions

    async def execute(self, command: PlanSessionCommand) -> Session:
        """Create the session in its planned state and store it.

        Raises:
            DuplicateAggregateError: a session already has that id.
            InvalidSemesterSetError: the semesters are missing, duplicated, or otherwise not
                a set a session can be subdivided by.
            InvalidAcademicYearError: the year is not one a session can start in.
            ValueError: a semester's ``ordinal`` is not one this context recognises.
        """
        session = Session.plan(
            session_id=command.session_id,
            academic_year=AcademicYear(command.academic_year),
            semesters=_semesters(command.semesters),
        )
        await self._sessions.add(session)
        return session


class OpenSession:
    """Open a planned session, announcing it.

    The only publisher of ``SessionOpened`` in the system. Billing charges every active account
    the session's fee on it, so this use case is the moment a cohort is billed — see the module
    docstring.
    """

    def __init__(
        self,
        sessions: SessionRepositoryPort,
        events: EventPublisherPort,
    ) -> None:
        self._sessions = sessions
        self._events = events

    async def execute(self, command: OpenSessionCommand) -> Session:
        """Open the session, store it, then announce it.

        **Saved before published**, which is the opposite of ``AcceptOffer``'s order and for
        the opposite reason: there is no idempotent healer here, and the failure to avoid is
        billing a cohort against a session the calendar does not record as open. A crash
        between the writes leaves a session open that nobody was charged for, which an
        administrator fixes by re-running the batch; publishing first would leave a thousand
        accounts charged for a session still stored as planned, and re-opening it would charge
        them again — the charge-once-per-``(kind, session_id)`` rule would catch the second
        round, but only after the first had gone out against a session nobody could see.

        Raises:
            SessionNotFoundError: no session is stored under that id.
            SessionAlreadyOpenError: the session has already been opened, or has closed.
        """
        session = await self._sessions.get(command.session_id)
        if session is None:
            raise SessionNotFoundError(f"no session stored with id {command.session_id!r}")

        event = session.open()
        await self._sessions.save(session)
        await self._events.publish(event)
        return session


def _semesters(planned: Iterable[PlannedSemester]) -> tuple[Semester, ...]:
    """Turn the command's primitives into the aggregate's semesters."""
    return tuple(
        Semester(semester.semester_id, SemesterOrdinal(semester.ordinal)) for semester in planned
    )
