"""Domain events published by the Faculty & Department context.

Past-tense facts, immutable once produced. Consumers never import these classes;
an outbound adapter serialises them at the boundary.
"""

from dataclasses import dataclass

from faculty_department.domain.values import AcademicYear


@dataclass(frozen=True)
class SessionOpened:
    """An academic session has opened. Billing batch-applies its fee schedule on this."""

    session_id: str
    academic_year: AcademicYear


@dataclass(frozen=True)
class GradeSubmitted:
    """A lecturer has submitted a grade for a student on a course they teach.

    ``grade`` is the raw score out of 100. Academic Records creates its record
    from this event and owns the mapping to letters and grade points.
    """

    student_id: str
    course_id: str
    semester_id: str
    grade: int
