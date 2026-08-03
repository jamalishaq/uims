"""The tables behind Faculty & Department's five repositories.

One ``MetaData`` per context, carrying a Postgres schema of the context's own name. The
boundary CLAUDE.md draws in ``src/`` is drawn again in the database: nothing here can join to
another context's rows by accident, because nothing here can see them without qualifying the
schema, and a query that did would be as visible in review as an import would be.

Core ``Table`` definitions rather than ORM models, and rather than imperative mapping onto the
aggregates. The aggregates are hand-written classes with private attributes, frozen value
objects, sets and tuples — ``Lecturer`` holds a ``set[CourseAssignment]`` of frozen
dataclasses, ``Session`` a sorted tuple of child entities — and mapping those imperatively
means either bending the domain to suit the mapper or fighting the mapper to keep the domain.
The translation is written out instead, in ``_mapping.py``, where it can be read.

Child rows carry ``ondelete="CASCADE"`` and are rewritten wholesale on every ``save``. An
aggregate is the consistency boundary (CLAUDE.md section 5), so its children have no life
apart from it: a lecturer's assignments are written as the set they now are rather than
diffed, which is both simpler and impossible to get half-right.
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
    UniqueConstraint,
)

SCHEMA = "faculty_department"

metadata = MetaData(schema=SCHEMA)

faculties = Table(
    "faculties",
    metadata,
    Column("faculty_id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("code", String, nullable=False),
    Column("ordinal", Integer, Identity(), nullable=False, unique=True),
)
"""``ordinal`` is what "in the order it was added" means once rows are involved.

Every ``list_*`` method on these ports promises insertion order, and a table has none —
``SELECT`` without ``ORDER BY`` may return rows in any order Postgres finds convenient, and
will start doing so the first time a row is updated. A serial column is the cheapest way to
keep a promise the in-memory adapter got for free from ``dict``.
"""

departments = Table(
    "departments",
    metadata,
    Column("department_id", String, primary_key=True),
    Column("faculty_id", String, nullable=False, index=True),
    Column("name", String, nullable=False),
    Column("code", String, nullable=False),
    Column("ordinal", Integer, Identity(), nullable=False, unique=True),
)
"""``faculty_id`` carries no foreign key, deliberately.

It names a faculty in this same context, so a constraint would be defensible here in a way it
never is across a boundary. It is left off so that every table in this package is written the
same way: identifiers are strings the repository does not vouch for, and ``list_for_faculty``
of an id nobody stored is an empty tuple rather than an error — which is what the port says.
"""

programs = Table(
    "programs",
    metadata,
    Column("program_id", String, primary_key=True),
    Column("department_id", String, nullable=False, index=True),
    Column("name", String, nullable=False),
    Column("code", String, nullable=False),
    Column("admitting", Boolean, nullable=False),
    Column("ordinal", Integer, Identity(), nullable=False, unique=True),
)

lecturers = Table(
    "lecturers",
    metadata,
    Column("lecturer_id", String, primary_key=True),
    Column("department_id", String, nullable=False, index=True),
    Column("full_name", String, nullable=False),
    Column("ordinal", Integer, Identity(), nullable=False, unique=True),
)

lecturer_assignments = Table(
    "lecturer_assignments",
    metadata,
    Column(
        "lecturer_id",
        String,
        ForeignKey(f"{SCHEMA}.lecturers.lecturer_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("course_id", String, primary_key=True),
    Column("session_id", String, primary_key=True),
)
"""Part of the ``Lecturer`` aggregate, which is why the port has no assignment repository.

The composite primary key is the aggregate's own invariant made a constraint: a lecturer
cannot hold one course twice in one session, which is what ``assign_to_course`` refuses.
"""

sessions = Table(
    "sessions",
    metadata,
    Column("session_id", String, primary_key=True),
    Column("start_year", Integer, nullable=False),
    Column("status", String, nullable=False),
    Column("ordinal", Integer, Identity(), nullable=False, unique=True),
)

semesters = Table(
    "semesters",
    metadata,
    Column("semester_id", String, primary_key=True),
    Column(
        "session_id",
        String,
        ForeignKey(f"{SCHEMA}.sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("ordinal", Integer, nullable=False),
    UniqueConstraint("session_id", "ordinal", name="uq_one_semester_per_ordinal"),
)
"""``Semester`` is a child entity with no identity outside its session, so it lives here.

The unique constraint says what ``_validated_semesters`` says: one first and one second
semester per session, and no more.
"""
