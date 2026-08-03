"""The academic calendar: sessions and the semesters that subdivide them.

Faculty & Department owns the calendar for the whole university. ``Session`` is
the aggregate root; ``Semester`` is a child entity that has no identity outside
its session, which is what makes "does this semester belong to this session?" a
question this aggregate can answer on its own.
"""

from collections.abc import Iterable
from enum import Enum

from faculty_department.domain.errors import (
    InvalidSemesterSetError,
    SessionAlreadyClosedError,
    SessionAlreadyOpenError,
    SessionNotOpenError,
)
from faculty_department.domain.events import SessionOpened
from faculty_department.domain.values import AcademicYear, require_identifier


class SemesterOrdinal(Enum):
    """A session is subdivided into exactly two semesters."""

    FIRST = 1
    SECOND = 2


class SessionStatus(Enum):
    """``PLANNED`` is the only state a session can be opened from; ``CLOSED`` is terminal."""

    PLANNED = "planned"
    OPEN = "open"
    CLOSED = "closed"


class Semester:
    """One half of a session. Identified by an id minted outside the domain."""

    def __init__(self, semester_id: str, ordinal: SemesterOrdinal) -> None:
        if not isinstance(ordinal, SemesterOrdinal):
            raise InvalidSemesterSetError("semester ordinal must be a SemesterOrdinal")
        self._semester_id = require_identifier(semester_id, "semester_id")
        self._ordinal = ordinal

    @property
    def semester_id(self) -> str:
        return self._semester_id

    @property
    def ordinal(self) -> SemesterOrdinal:
        return self._ordinal

    def __repr__(self) -> str:
        return f"Semester(semester_id={self._semester_id!r}, ordinal={self._ordinal.name})"


class Session:
    """An academic year (e.g. 2026/2027) and its two semesters."""

    def __init__(
        self,
        session_id: str,
        academic_year: AcademicYear,
        semesters: Iterable[Semester],
    ) -> None:
        if not isinstance(academic_year, AcademicYear):
            raise InvalidSemesterSetError("academic_year must be an AcademicYear")
        self._session_id = require_identifier(session_id, "session_id")
        self._academic_year = academic_year
        self._semesters = _validated_semesters(semesters)
        self._status = SessionStatus.PLANNED

    @classmethod
    def plan(
        cls,
        session_id: str,
        academic_year: AcademicYear,
        semesters: Iterable[Semester],
    ) -> "Session":
        """Define a future session. It is not open, so nothing may be graded against it yet."""
        return cls(session_id, academic_year, semesters)

    @classmethod
    def restore(
        cls,
        session_id: str,
        academic_year: AcademicYear,
        semesters: Iterable[Semester],
        status: SessionStatus,
    ) -> "Session":
        """Rebuild a session from stored state. A persistence adapter is the only caller.

        The status cannot be reached through :meth:`plan`, because a stored session may
        already be open or closed and :meth:`open` announces a fact that has already
        happened — replaying it on load would publish ``SessionOpened`` to a university that
        opened the session last September.

        This is the same door ``MatricSequence.restore`` opens in Student Profile, and it is
        kept just as narrow: the argument is checked, so a row carrying a status this class
        does not recognise is refused here rather than becoming a session in a state no
        transition could have produced.
        """
        if not isinstance(status, SessionStatus):
            raise InvalidSemesterSetError(f"stored status {status!r} is not a SessionStatus")
        session = cls(session_id, academic_year, semesters)
        session._status = status
        return session

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def academic_year(self) -> AcademicYear:
        return self._academic_year

    @property
    def status(self) -> SessionStatus:
        return self._status

    @property
    def is_open(self) -> bool:
        return self._status is SessionStatus.OPEN

    @property
    def semesters(self) -> tuple[Semester, ...]:
        """The session's semesters in ordinal order. A copy: internals do not leak."""
        return self._semesters

    def has_semester(self, semester_id: str) -> bool:
        return any(semester.semester_id == semester_id for semester in self._semesters)

    def open(self) -> SessionOpened:
        """Open the session for the academic year, announcing it to the university."""
        if self._status is SessionStatus.OPEN:
            raise SessionAlreadyOpenError(f"session {self._session_id} is already open")
        if self._status is SessionStatus.CLOSED:
            raise SessionAlreadyClosedError(
                f"session {self._session_id} is closed and cannot reopen"
            )
        self._status = SessionStatus.OPEN
        return SessionOpened(session_id=self._session_id, academic_year=self._academic_year)

    def close(self) -> None:
        """Close the session. Terminal: a closed session accepts no further grades."""
        if self._status is SessionStatus.CLOSED:
            raise SessionAlreadyClosedError(f"session {self._session_id} is already closed")
        if self._status is not SessionStatus.OPEN:
            raise SessionNotOpenError(f"session {self._session_id} was never opened")
        self._status = SessionStatus.CLOSED

    def __repr__(self) -> str:
        return (
            f"Session(session_id={self._session_id!r}, "
            f"academic_year={self._academic_year.label!r}, status={self._status.name})"
        )


def _validated_semesters(semesters: Iterable[Semester]) -> tuple[Semester, ...]:
    """Exactly one first and one second semester, with distinct ids."""
    ordered = tuple(semesters)
    if any(not isinstance(semester, Semester) for semester in ordered):
        raise InvalidSemesterSetError("semesters must all be Semester instances")

    ordinals = [semester.ordinal for semester in ordered]
    if sorted(ordinals, key=lambda o: o.value) != sorted(SemesterOrdinal, key=lambda o: o.value):
        raise InvalidSemesterSetError(
            "a session has exactly one first and one second semester, got "
            f"{[o.name for o in ordinals]}"
        )

    ids = [semester.semester_id for semester in ordered]
    if len(set(ids)) != len(ids):
        raise InvalidSemesterSetError(f"semester ids must be distinct, got {ids}")

    return tuple(sorted(ordered, key=lambda semester: semester.ordinal.value))
