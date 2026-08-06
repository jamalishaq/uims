"""Primitives-shaped projections of what this context's use cases return.

Everything downstream of Faculty & Department reads it through one of these. That is not an
accident of the HTTP phase: this is the most-queried context in the system (the reason the
playbook built it first), and the two query ports pointed at it —  Admissions'
``ProgramInfoPort`` and Student Profile's ``DepartmentCodePort`` — are satisfied by adapters
that must not import a ``Program``, a ``Department`` or a ``Session``. A flat view is what
crosses instead, and the consuming adapter translates it into its own vocabulary.

So these are load-bearing in a way the other contexts' views are not: they are the published
shape of this context, and widening one is a change other contexts can see.
"""

from dataclasses import dataclass

from faculty_department.domain.department import Department
from faculty_department.domain.events import GradeSubmitted
from faculty_department.domain.faculty import Faculty
from faculty_department.domain.lecturer import Lecturer
from faculty_department.domain.program import Program
from faculty_department.domain.session import Session


@dataclass(frozen=True)
class GradeSubmittedView:
    """What a lecturer's submission recorded, flat.

    ``SubmitGrade`` returns the ``GradeSubmitted`` event itself, which is the right thing for
    the publisher to hand the bus and the wrong thing to put on a wire twice. ``grade`` keeps
    the event's name for the raw score, because renaming a published field in a projection is
    how two vocabularies start.
    """

    student_id: str
    course_id: str
    semester_id: str
    grade: int

    @classmethod
    def of(cls, event: GradeSubmitted) -> "GradeSubmittedView":
        return cls(
            student_id=event.student_id,
            course_id=event.course_id,
            semester_id=event.semester_id,
            grade=event.grade,
        )


@dataclass(frozen=True)
class ProgramPlacementView:
    """Where a program sits and whether it is taking anybody, for one session.

    One view answering two ports, because they are two readings of one join: a program, the
    department behind it, and the session the question is asked about. Splitting it in two
    would mean two reads of the same three rows and two chances for them to disagree about
    which department a program belongs to.

    ``department_code`` is Faculty & Department's own alphabetic code (``CSC``). The four
    numeric digits a matric number carries are Student Profile's adapter's translation of it,
    and CLAUDE.md section 3 is explicit that this is the one place that mapping lives — so it
    is deliberately *not* done here.

    ``is_admitting`` is the program's session-less flag, reported as-is. Admissions asks per
    session and reconciles the two in its own adapter; that is what its port's docstring
    promises, and answering a session-shaped question here would move the reconciliation into
    the context that does not own the question.
    """

    program_id: str
    department_id: str
    department_code: str
    faculty_id: str
    name: str
    code: str
    is_admitting: bool
    session_id: str
    session_start_year: int
    session_label: str
    session_is_open: bool


@dataclass(frozen=True)
class FacultyView:
    """A faculty, flat. The top of the structure everything else hangs off."""

    faculty_id: str
    name: str
    code: str

    @classmethod
    def of(cls, faculty: Faculty) -> "FacultyView":
        return cls(faculty_id=faculty.faculty_id, name=faculty.name, code=faculty.code)


@dataclass(frozen=True)
class DepartmentView:
    """A department and the faculty it sits in.

    ``code`` is this context's alphabetic code (``CSC``). The four numeric digits a matric
    number carries are Student Profile's translation of it, and deliberately not here — the
    same line ``ProgramPlacementView`` already holds.
    """

    department_id: str
    faculty_id: str
    name: str
    code: str

    @classmethod
    def of(cls, department: Department) -> "DepartmentView":
        return cls(
            department_id=department.department_id,
            faculty_id=department.faculty_id,
            name=department.name,
            code=department.code,
        )


@dataclass(frozen=True)
class ProgramView:
    """A program, its department, and whether it is taking applications.

    ``is_admitting`` is the session-less flag as this context holds it. Admissions asks per
    session and reconciles the two in its own adapter, which is where that judgement belongs.
    """

    program_id: str
    department_id: str
    name: str
    code: str
    is_admitting: bool

    @classmethod
    def of(cls, program: Program) -> "ProgramView":
        return cls(
            program_id=program.program_id,
            department_id=program.department_id,
            name=program.name,
            code=program.code,
            is_admitting=program.is_admitting,
        )

    @classmethod
    def of_each(cls, programs: tuple[Program, ...]) -> tuple["ProgramView", ...]:
        return tuple(cls.of(program) for program in programs)


@dataclass(frozen=True)
class SemesterView:
    """One semester of a session.

    ``ordinal`` is the enum's value — ``1`` for first, ``2`` for second — rather than a name.
    That is what ``SemesterOrdinal`` holds, and projecting a prettier string would invent a
    second vocabulary for the same fact.
    """

    semester_id: str
    ordinal: int


@dataclass(frozen=True)
class SessionView:
    """An academic session, its semesters, and whether it has opened.

    Semesters come back in the order the session holds them, which the aggregate validates as
    the ordinal order — a caller can rely on first semester coming first.
    """

    session_id: str
    academic_year: int
    label: str
    status: str
    is_open: bool
    semesters: tuple[SemesterView, ...]

    @classmethod
    def of(cls, session: Session) -> "SessionView":
        return cls(
            session_id=session.session_id,
            academic_year=session.academic_year.start_year,
            label=session.academic_year.label,
            status=session.status.value,
            is_open=session.is_open,
            semesters=tuple(
                SemesterView(semester_id=semester.semester_id, ordinal=semester.ordinal.value)
                for semester in session.semesters
            ),
        )


@dataclass(frozen=True)
class CourseAssignmentView:
    """One course a lecturer teaches, in one session."""

    course_id: str
    session_id: str


@dataclass(frozen=True)
class LecturerView:
    """A lecturer and what they teach.

    ``assignments`` is sorted rather than left in set order: the aggregate holds a
    ``frozenset``, which has none, and an unstable response body cannot be cached or diffed.
    """

    lecturer_id: str
    department_id: str
    full_name: str
    assignments: tuple[CourseAssignmentView, ...]

    @classmethod
    def of(cls, lecturer: Lecturer) -> "LecturerView":
        return cls(
            lecturer_id=lecturer.lecturer_id,
            department_id=lecturer.department_id,
            full_name=lecturer.full_name,
            assignments=tuple(
                CourseAssignmentView(course_id=course_id, session_id=session_id)
                for course_id, session_id in sorted(
                    (assignment.course_id, assignment.session_id)
                    for assignment in lecturer.assignments
                )
            ),
        )

    @classmethod
    def of_each(cls, lecturers: tuple[Lecturer, ...]) -> tuple["LecturerView", ...]:
        return tuple(cls.of(lecturer) for lecturer in lecturers)
