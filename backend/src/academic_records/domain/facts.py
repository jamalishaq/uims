"""What other contexts supply, said in Academic Records' own words.

There is exactly one of these, and its existence is the answer to a question the event
does not answer. ``GradeSubmitted`` carries ``(student_id, course_id, semester_id,
grade)`` and no credit units, because Faculty & Department does not own credit units —
Course Catalog does. A CGPA is a weighted average and the weight is the units, so this
context has to ask.

It lives in ``domain/`` rather than beside the port for the reason
``enrollment/domain/facts.py`` gives: the domain layer may not import ``ports/``
(CLAUDE.md section 4), the aggregate reads this type directly, and a second definition out
there would mean a second translation, with the two free to drift.

The narrowing is severe and deliberate. Over in Course Catalog a ``Course`` has a code, a
title, an offering department, a prerequisite chain and a retirement flag. A transcript
line needs one number off it. In particular there is **no active flag**: Course Catalog
retires courses instead of deleting them precisely because transcripts refer to courses
no longer taught, and a retired course must keep resolving here long after it has stopped
being registrable over in Enrollment.
"""

from dataclasses import dataclass

from academic_records.domain.values import require_credit_units, require_identifier


@dataclass(frozen=True)
class CourseCredits:
    """What a course is worth, which is all this context needs to know about one.

    Read once, at the moment a grade is recorded, and then snapshotted onto the transcript
    line — the same rule Enrollment applies to a registration's units, and for a stronger
    reason. Course Catalog can amend a course from three units to four; a transcript that
    re-read them would silently rewrite the CGPA of every student who has already
    graduated.
    """

    course_id: str
    credit_units: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "course_id", require_identifier(self.course_id, "course_id"))
        object.__setattr__(
            self, "credit_units", require_credit_units(self.credit_units, "credit units")
        )
