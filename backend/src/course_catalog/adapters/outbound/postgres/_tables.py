"""The tables behind the catalog.

One aggregate, and one child table for the prerequisite ids it holds. The child rows carry a
``position`` because ``Course.prerequisite_ids`` promises "the order they were added" and
``PrerequisiteGraph`` walks the chain breadth-first in that order — a set would give a
different answer to "what comes immediately before this" on every read.

``code`` is uniquely indexed. The catalog's own ``RegisterCourse`` already refuses a duplicate
code by asking ``find_by_code`` first, but that check reads and then writes, and two
registrars filing the same code at once would both pass it. The constraint is what actually
holds, and the read is what turns it into a decent error message.
"""

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Identity,
    Integer,
    MetaData,
    String,
    Table,
)

SCHEMA = "course_catalog"

metadata = MetaData(schema=SCHEMA)

courses = Table(
    "courses",
    metadata,
    Column("course_id", String, primary_key=True),
    Column("department_id", String, nullable=False, index=True),
    Column("code", String, nullable=False, unique=True),
    Column("title", String, nullable=False),
    Column("credit_units", Integer, nullable=False),
    Column("active", Boolean, nullable=False),
    Column("ordinal", Integer, Identity(), nullable=False, unique=True),
)
"""``active`` rather than a deletion: courses are retired, never removed.

The port says so — "an id that once resolved must keep resolving", because Enrollment and
Academic Records hold course ids for as long as a transcript exists. There is no ``DELETE``
anywhere in this package.
"""

course_prerequisites = Table(
    "course_prerequisites",
    metadata,
    Column(
        "course_id",
        String,
        ForeignKey(f"{SCHEMA}.courses.course_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("prerequisite_id", String, primary_key=True),
    Column("position", Integer, nullable=False),
)
"""``prerequisite_id`` has no foreign key, and that is not an oversight.

``AddPrerequisite`` checks that the prerequisite is in the catalog before wiring it in, so the
rule is enforced where the error message can say something useful. A constraint here would
also refuse the row, but it would refuse it as an integrity error at write time — and
``PrerequisiteGraph`` is explicitly written to tolerate an id that does not resolve, because
"whether a stored id ought to resolve is a question about what this system holds, and the
answer to that is the application layer's to give".
"""
