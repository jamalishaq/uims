"""The tables behind the student register and the intake counters.

Two aggregates, and the second one is the reason this context is worth reading. A
``MatricSequence`` row is the shared state that the in-memory adapter's ``threading.Lock``
stood in for — its own docstring says so: "Phase 6 replaces both mechanisms at once — the row
is the shared state and ``SELECT ... FOR UPDATE`` is the lock".
"""

from sqlalchemy import (
    Column,
    Date,
    Identity,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)

SCHEMA = "student_profile"

metadata = MetaData(schema=SCHEMA)

students = Table(
    "students",
    metadata,
    Column("student_id", String, primary_key=True),
    Column("matric_number", String, nullable=False, unique=True),
    Column("full_name", String, nullable=False),
    Column("date_of_birth", Date, nullable=True),
    Column("email", String, nullable=True),
    Column("phone_number", String, nullable=True),
    Column("program_id", String, nullable=False),
    Column("entry_session_id", String, nullable=False),
    Column("entry_level", Integer, nullable=False),
    Column("applicant_id", String, nullable=True, unique=True),
    Column("ordinal", Integer, Identity(), nullable=False, unique=True),
)
"""Two unique constraints doing real work, and one column that is deliberately nullable.

``matric_number`` is unique because that is the invariant the whole of ``MatricSequence``
exists to protect: "by the time anyone notices, two students are answering to one identifier
and every downstream context has already keyed rows on it". A counter that failed would still
be caught here.

``applicant_id`` is unique because ``find_by_applicant`` is what makes consuming
``StudentMatriculated`` idempotent, and a second row for one applicant would be the duplicate
matriculation that lookup exists to prevent. It is nullable because "a student registered by
hand never had an applicant" — and in Postgres many rows may be NULL under a unique
constraint, which is exactly the behaviour wanted.

``BioData`` is flattened into columns rather than stored as JSON. It is a value object with
four named fields, and a registrar looking for a phone number should not have to know how this
adapter chose to encode one.
"""

matric_sequences = Table(
    "matric_sequences",
    metadata,
    Column("department_code", String, primary_key=True),
    Column("entry_year", Integer, primary_key=True),
    Column("issued", Integer, nullable=False),
    Column("ordinal", Integer, Identity(), nullable=False, unique=True),
    UniqueConstraint("department_code", "entry_year", name="uq_one_counter_per_intake"),
)
"""One row per department per year, and the primary key says so.

There is no ``add`` on this port — "a sequence is never created deliberately by anyone, it
comes into existence because a department admitted somebody" — so the row is created by an
upsert inside ``get_or_start``, and the key is what makes that upsert safe.
"""
