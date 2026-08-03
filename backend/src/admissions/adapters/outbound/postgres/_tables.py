"""The tables behind Admissions' four repositories.

Three of the four are keyed by ``(program_id, session_id)`` rather than by an id of their own,
and that is not an implementation detail — the ports say so, at length, and each gives the
same reason: the data is session-scoped, and "publishing this session's requirement must not
overwrite last session's". The composite primary keys here are that rule made a constraint.

Two of them hold policy rather than aggregates in the usual sense, and both carry ordered or
set-valued children that the aggregate normalises on the way in. Nothing is stored as JSON:
the alternatives are a tuple whose *order is the whole content*, and a subject group is a set
somebody will eventually want to query.
"""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Integer,
    MetaData,
    String,
    Table,
)

SCHEMA = "admissions"

metadata = MetaData(schema=SCHEMA)

applicants = Table(
    "applicants",
    metadata,
    Column("applicant_id", String, primary_key=True),
    Column("applied_program_id", String, nullable=False),
    Column("offered_program_id", String, nullable=True),
    Column("session_id", String, nullable=False, index=True),
    Column("full_name", String, nullable=False),
    Column("date_of_birth", Date, nullable=True),
    Column("email", String, nullable=True),
    Column("phone_number", String, nullable=True),
    Column("status", String, nullable=False),
    Column("fee_cleared", Boolean, nullable=False),
    Column("ordinal", Integer, Identity(), nullable=False, unique=True),
)
"""Two program columns, because the aggregate has two and collapsing them loses a fact.

``applied_program_id`` is what the applicant asked for and never changes; ``offered_program_id``
is what the university actually offered, which may be an alternative. The docstring on
``Applicant`` is explicit that collapsing them "would lose the applicant's own account of
events the moment an alternative offer was made", and a schema that stored one column would
do exactly that.
"""

utme_scores = Table(
    "utme_scores",
    metadata,
    Column(
        "applicant_id",
        String,
        ForeignKey(f"{SCHEMA}.applicants.applicant_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("subject", String, primary_key=True),
    Column("position", Integer, nullable=False),
    Column("score", Integer, nullable=False),
)
"""``subject`` in the primary key is ``UtmeResult``'s distinctness rule, enforced twice.

The value object refuses a result listing Chemistry twice, "because one score would be counted
against two requirements". The constraint says the same thing about the rows.

``position`` preserves the order the subjects were given in. Nothing reads it — ``UtmeResult``
exposes a ``frozenset`` of subjects and a sum — but a result read back in a different order
from the one it was entered in would be a different value object by ``==``, and tests compare
them.
"""

entry_requirements = Table(
    "entry_requirements",
    metadata,
    Column("program_id", String, primary_key=True),
    Column("session_id", String, primary_key=True),
    Column("ordinal", Integer, Identity(), nullable=False, unique=True),
)

required_subjects = Table(
    "required_subjects",
    metadata,
    Column("program_id", String, primary_key=True),
    Column("session_id", String, primary_key=True),
    Column("subject", String, primary_key=True),
    ForeignKeyConstraint(
        ["program_id", "session_id"],
        [f"{SCHEMA}.entry_requirements.program_id", f"{SCHEMA}.entry_requirements.session_id"],
        ondelete="CASCADE",
    ),
)
"""A set, and stored as one: no position column, because ``required_subjects`` is a frozenset.

Where ``AlternativeProgramPolicy`` gets a position and this does not is the difference the two
domain classes already draw. Order is the whole content of a fallback chain and none of the
content of a set of required subjects.
"""

subject_groups = Table(
    "subject_groups",
    metadata,
    Column("program_id", String, primary_key=True),
    Column("session_id", String, primary_key=True),
    Column("group_position", Integer, primary_key=True),
    Column("subject", String, primary_key=True),
    ForeignKeyConstraint(
        ["program_id", "session_id"],
        [f"{SCHEMA}.entry_requirements.program_id", f"{SCHEMA}.entry_requirements.session_id"],
        ondelete="CASCADE",
    ),
)
"""One row per option per group, with ``group_position`` keeping the groups apart.

A requirement may hold several one-of groups — "one of {Chemistry, Biology}" and "one of
{Physics, Geography}" are two different demands — so the options cannot be flattened into a
single set without merging two questions into one.
"""

admission_cycles = Table(
    "admission_cycles",
    metadata,
    Column("program_id", String, primary_key=True),
    Column("session_id", String, primary_key=True),
    Column("quota", Integer, nullable=False),
    Column("offers_made", Integer, nullable=False),
    Column("ordinal", Integer, Identity(), nullable=False, unique=True),
)
"""Where the quota invariant lands in the database.

``AdmissionCycle.offer()`` closes the read-check-write gap *within* the aggregate; keeping two
officers from claiming the same last place across two processes is this adapter's to arrange,
and the port says so. The row is the shared state and the transaction around ``save`` is what
serialises the claim.
"""

alternative_policies = Table(
    "alternative_policies",
    metadata,
    Column("program_id", String, primary_key=True),
    Column("session_id", String, primary_key=True),
    Column("ordinal", Integer, Identity(), nullable=False, unique=True),
)

alternative_programs = Table(
    "alternative_programs",
    metadata,
    Column("program_id", String, primary_key=True),
    Column("session_id", String, primary_key=True),
    Column("position", Integer, primary_key=True),
    Column("alternative_program_id", String, nullable=False),
    ForeignKeyConstraint(
        ["program_id", "session_id"],
        [
            f"{SCHEMA}.alternative_policies.program_id",
            f"{SCHEMA}.alternative_policies.session_id",
        ],
        ondelete="CASCADE",
    ),
)
"""``position`` is in the primary key because order *is* the policy.

"First qualifying program with a place left gets the applicant, so re-ordering the list
changes who ends up where — a set would lose the decision and let the answer depend on hash
order." A table has no order either, so the position is stored rather than hoped for.
"""
