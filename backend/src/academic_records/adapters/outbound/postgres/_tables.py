"""The tables behind the one aggregate this context holds.

A record, its transcript lines, and the audit trail of every correction ever applied to them.
Three tables for one aggregate, because a transcript line and a correction are different kinds
of thing that happen to hang off the same student.

Nothing here is ever deleted. The port is explicit about it — "a transcript is the university's
permanent statement about what somebody achieved, and is asked for by employers and other
institutions decades after the student leaves" — so there is no ``remove`` and the only
``DELETE`` in this package is the one that rewrites the child rows of a record being saved.
"""

from sqlalchemy import (
    Column,
    ForeignKey,
    Identity,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    UniqueConstraint,
)

SCHEMA = "academic_records"

metadata = MetaData(schema=SCHEMA)

academic_records = Table(
    "academic_records",
    metadata,
    Column("student_id", String, primary_key=True),
    Column("ordinal", Integer, Identity(), nullable=False, unique=True),
)
"""Keyed by the student, and holding nothing else.

"There is exactly one record per student and the aggregate is only ever reached by asking
about a person. A second key would be a second thing to look a record up by and a second thing
to get wrong." Everything the record *says* is derived from its lines, so there is no CGPA
column here — a stored figure "could fall out of step", and Transcript recomputes on read.
"""

course_grades = Table(
    "course_grades",
    metadata,
    Column(
        "student_id",
        String,
        ForeignKey(f"{SCHEMA}.academic_records.student_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("course_id", String, primary_key=True),
    Column("semester_id", String, primary_key=True),
    Column("position", Integer, nullable=False),
    Column("score", Integer, nullable=False),
    Column("credit_units", Integer, nullable=False),
    Column("letter", String, nullable=False),
    Column("grade_point", Numeric(3, 2), nullable=False),
    UniqueConstraint("student_id", "position", name="uq_one_line_per_position"),
)
"""``(course_id, semester_id)`` in the key is the carry-over rule, needing no code again.

"A course sat again in a *different* semester is a different line, and both count towards the
CGPA." The key permits exactly that and refuses the thing ``record_grade`` refuses: a second,
different score for one course in one semester.

**``letter`` and ``grade_point`` are stored rather than re-derived**, which looks like
duplication and is the opposite. ``AcademicRecord`` holds the scale its grades were awarded on
so that "a student graded under one scale keeps the letters they were given if the university
adopts another"; re-deriving on read would throw that away the day the scale changed.
``Numeric`` and never a float, for the reason ``transcript.py`` gives at length: a CGPA is
arithmetic somebody checks by hand.
"""

grade_corrections = Table(
    "grade_corrections",
    metadata,
    Column(
        "student_id",
        String,
        ForeignKey(f"{SCHEMA}.academic_records.student_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("position", Integer, primary_key=True),
    Column("course_id", String, nullable=False),
    Column("semester_id", String, nullable=False),
    Column("previous_score", Integer, nullable=False),
    Column("corrected_score", Integer, nullable=False),
    Column("reason", String, nullable=False),
    Column("authorized_by", String, nullable=False),
)
"""Keyed by position rather than by the line corrected, because a line may be corrected twice.

"Every correction is history. The second does not overwrite the record of the first" — so the
course and semester are ordinary columns here and the sequence is the key.
"""
