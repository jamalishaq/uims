"""The tables behind Enrollment's two repositories.

``Term`` is Enrollment's own flat reading of Faculty & Department's calendar, and it is stored
flat: three columns rather than a composite type or a serialised blob. It is a frozen value
object with three fields and it keys an offering, so a query that wants "every registration in
this session" should be able to say so without parsing anything.

Both tables carry the invariant their aggregate exists to protect. ``CourseOffering``'s
capacity check and ``AdmissionCycle``'s quota check are the same argument made twice, and both
end up here the same way: the row is the shared state, and the transaction around ``save`` is
what stops two students taking the last seat.
"""

from sqlalchemy import (
    Boolean,
    Column,
    Identity,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)

SCHEMA = "enrollment"

metadata = MetaData(schema=SCHEMA)

enrollments = Table(
    "enrollments",
    metadata,
    Column("enrollment_id", String, primary_key=True),
    Column("student_id", String, nullable=False, index=True),
    Column("course_id", String, nullable=False, index=True),
    Column("session_id", String, nullable=False),
    Column("semester_id", String, nullable=False),
    Column("term_ordinal", Integer, nullable=False),
    Column("credit_units", Integer, nullable=False),
    Column("is_carry_over", Boolean, nullable=False),
    Column("status", String, nullable=False),
    Column("ordinal", Integer, Identity(), nullable=False, unique=True),
)
"""``credit_units`` is a column and not a lookup, which is the whole point of the snapshot.

"A course later re-valued must not rewrite a term already registered." Reading the units back
from Course Catalog would undo that on every read, so they are written down at registration
and never consulted again.

There is no unique constraint on ``(student_id, course_id, session_id, semester_id)``, and
that is deliberate: a carry-over is the *same* student registering the *same* course again,
and a constraint spanning the term would still be wrong the day somebody re-sits within one.
Whether a duplicate registration is allowed is ``EligibilityRule``'s judgement — it reads
``already_registered`` and refuses — and a constraint here would move that decision into the
schema and change the error a student sees.
"""

course_offerings = Table(
    "course_offerings",
    metadata,
    Column("course_id", String, primary_key=True),
    Column("session_id", String, primary_key=True),
    Column("semester_id", String, primary_key=True),
    Column("term_ordinal", Integer, nullable=False),
    Column("capacity", Integer, nullable=False),
    Column("seats_taken", Integer, nullable=False),
    Column("ordinal", Integer, Identity(), nullable=False, unique=True),
    UniqueConstraint("course_id", "session_id", "semester_id", name="uq_one_offering_per_term"),
)
"""Keyed by ``(course_id, term)`` because that is the offering's identity.

"The same course run again next semester is a different offering with its own seats, and a
registration always names both." The three columns of the term are in the primary key, and
``term_ordinal`` rides along beside them because ``Term`` carries it and Billing's clearance
rule turns on it.
"""
