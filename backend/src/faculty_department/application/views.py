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

from faculty_department.domain.events import GradeSubmitted


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
