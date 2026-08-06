"""What changes about a lecturer: their staff record, and the courses they teach.

Course assignments have been on the aggregate since the first phase and are what
``SubmitGrade`` authorizes against — "does this lecturer teach this course?" — but nothing
could set one. A lecturer registered through the API taught nothing, forever, which made the
grade-submission route unreachable for anybody not seeded by hand.

**Assignments are scoped to a session**, so this runs every year rather than once. Teaching
CSC101 in 2026/2027 says nothing about 2027/2028, and that is what stops somebody grading a
course forever on the strength of having taught it once.

**Amending the profile replaces it wholesale.** Omitting a field clears it, because that is
what the form does — see ``Lecturer.amend_profile`` on why this is not a promotion and records
no history.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from faculty_department.application.errors import InvalidRankError, LecturerNotFoundError
from faculty_department.domain.lecturer import CourseAssignment, Lecturer
from faculty_department.domain.values import EmploymentStatus, Qualification, Rank
from faculty_department.ports.lecturer_repository import LecturerRepositoryPort


@dataclass(frozen=True)
class QualificationInput:
    """One degree, in primitives, as a transport carries it."""

    degree: str
    discipline: str
    institution: str
    year: int


@dataclass(frozen=True)
class AmendLecturerProfileCommand:
    """Everything on file about a member of staff, as it should now read.

    ``rank`` and ``employment_status`` are the enums' wire values (``"senior lecturer"``,
    ``"full-time"``) rather than the enums, because a command is what crosses from a transport.
    An unrecognised value raises rather than being dropped: a rank silently discarded would
    leave the record saying nothing, which reads identically to nobody having filled it in.

    All three default to empty, which **clears** rather than preserves. This is a replacement.
    """

    lecturer_id: str
    rank: str | None = None
    employment_status: str | None = None
    qualifications: tuple[QualificationInput, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AssignLecturerToCourseCommand:
    """Put a lecturer in charge of one course for one session."""

    lecturer_id: str
    course_id: str
    session_id: str


@dataclass(frozen=True)
class WithdrawLecturerFromCourseCommand:
    """Take a course off a lecturer for one session."""

    lecturer_id: str
    course_id: str
    session_id: str


class AmendLecturerProfile:
    """Replace what is on file about a lecturer."""

    def __init__(self, lecturers: LecturerRepositoryPort) -> None:
        self._lecturers = lecturers

    async def execute(self, command: AmendLecturerProfileCommand) -> Lecturer:
        """Set rank, employment status and qualifications, then store.

        Raises:
            LecturerNotFoundError: no lecturer is stored under that id.
            InvalidRankError: ``rank`` or ``employment_status`` is not one this university has.
            InvalidQualificationError: a degree is missing a field or dated in the future.
            InvalidLecturerProfileError: a qualification is listed twice.
        """
        lecturer = await self._find(command.lecturer_id)
        lecturer.amend_profile(
            rank=_rank(command.rank),
            employment_status=_employment_status(command.employment_status),
            qualifications=_qualifications(command.qualifications),
        )
        await self._lecturers.save(lecturer)
        return lecturer

    async def _find(self, lecturer_id: str) -> Lecturer:
        lecturer = await self._lecturers.get(lecturer_id)
        if lecturer is None:
            raise LecturerNotFoundError(f"no lecturer stored with id {lecturer_id!r}")
        return lecturer


class AssignLecturerToCourse:
    """Give a lecturer a course for a session."""

    def __init__(self, lecturers: LecturerRepositoryPort) -> None:
        self._lecturers = lecturers

    async def execute(self, command: AssignLecturerToCourseCommand) -> CourseAssignment:
        """Record the assignment and store the lecturer.

        The course id is Course Catalog's and **is not checked against it**. Adding a query
        port for that would be a new cross-context dependency (CLAUDE.md section 6) to catch a
        typo, and the failure it would prevent is already visible — a lecturer assigned to a
        course that does not exist cannot submit a grade anybody records, because Academic
        Records refuses a course the catalog has no credit units for.

        Raises:
            LecturerNotFoundError: no lecturer is stored under that id.
            DuplicateCourseAssignmentError: they already teach it in that session.
            MissingIdentifierError: the course or session id is blank.
        """
        lecturer = await self._find(command.lecturer_id)
        assignment = lecturer.assign_to_course(command.course_id, command.session_id)
        await self._lecturers.save(lecturer)
        return assignment

    async def _find(self, lecturer_id: str) -> Lecturer:
        lecturer = await self._lecturers.get(lecturer_id)
        if lecturer is None:
            raise LecturerNotFoundError(f"no lecturer stored with id {lecturer_id!r}")
        return lecturer


class WithdrawLecturerFromCourse:
    """Take a course off a lecturer for a session."""

    def __init__(self, lecturers: LecturerRepositoryPort) -> None:
        self._lecturers = lecturers

    async def execute(self, command: WithdrawLecturerFromCourseCommand) -> Lecturer:
        """Drop the assignment and store the lecturer.

        Grades already submitted are untouched. They live in Academic Records, which was told
        a fact rather than handed a permission — withdrawing somebody from a course they
        taught last semester must not unpick a transcript.

        Raises:
            LecturerNotFoundError: no lecturer is stored under that id.
            LecturerNotAssignedToCourseError: they do not teach it in that session.
        """
        lecturer = await self._find(command.lecturer_id)
        lecturer.withdraw_from_course(command.course_id, command.session_id)
        await self._lecturers.save(lecturer)
        return lecturer

    async def _find(self, lecturer_id: str) -> Lecturer:
        lecturer = await self._lecturers.get(lecturer_id)
        if lecturer is None:
            raise LecturerNotFoundError(f"no lecturer stored with id {lecturer_id!r}")
        return lecturer


def _rank(value: str | None) -> Rank | None:
    if value is None:
        return None
    try:
        return Rank(value)
    except ValueError as unknown:
        known = ", ".join(rank.value for rank in Rank)
        raise InvalidRankError(f"{value!r} is not a rank; expected one of {known}") from unknown


def _employment_status(value: str | None) -> EmploymentStatus | None:
    if value is None:
        return None
    try:
        return EmploymentStatus(value)
    except ValueError as unknown:
        known = ", ".join(status.value for status in EmploymentStatus)
        raise InvalidRankError(
            f"{value!r} is not an employment status; expected one of {known}"
        ) from unknown


def _qualifications(held: Iterable[QualificationInput]) -> tuple[Qualification, ...]:
    return tuple(
        Qualification(
            degree=one.degree,
            discipline=one.discipline,
            institution=one.institution,
            year=one.year,
        )
        for one in held
    )
