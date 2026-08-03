"""The tables behind Billing's three repositories.

Money is ``NUMERIC(14, 2)`` everywhere and never a float. ``Money`` refuses a float in the
constructor "because by the time it arrives the precision is already gone", and a column that
undid that on the way to disk would make the value object decorative. Two decimal places is
kobo, which is the smallest unit anybody can actually pay.

The two keys worth reading are the account's and the intent's, and both are named by their
ports. An account is keyed by a *party* and answers to a second id once the matric number is
linked; an intent is keyed by the gateway's own reference, which is also the ``gateway_ref``
on the resulting payment — "one key across both aggregates is what makes the whole path
idempotent without a de-duplication table".
"""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    UniqueConstraint,
)

SCHEMA = "billing"

metadata = MetaData(schema=SCHEMA)

MONEY = Numeric(14, 2)

accounts = Table(
    "accounts",
    metadata,
    Column("party_id", String, primary_key=True),
    Column("student_id", String, nullable=True, unique=True),
    Column("program_id", String, nullable=False),
    Column("level", Integer, nullable=False),
    Column("credit_balance", MONEY, nullable=False),
    Column("ordinal", Integer, Identity(), nullable=False, unique=True),
)
"""``student_id`` is the second index the port says this abstraction costs.

"``get`` resolves **either** of an account's ids... An adapter implementing this against a
table needs a second index; that is the cost of the party-id abstraction and it is paid here
rather than by every caller." Unique, because ``link_student_id`` refuses to point two ledgers
at one person, and nullable because a party is only their applicant id until they matriculate.

``credit_balance`` is stored rather than derived. It is not redundant with the payments and
the allocations: it is the part of what arrived that no charge was waiting for, and which
charge absorbed what is a decision the account made at allocation time. Recomputing it would
mean re-deciding it.
"""

charges = Table(
    "charges",
    metadata,
    Column(
        "party_id",
        String,
        ForeignKey(f"{SCHEMA}.accounts.party_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("kind", String, primary_key=True),
    Column("session_id", String, primary_key=True),
    Column("position", Integer, nullable=False),
    Column("amount", MONEY, nullable=False),
    Column("allocated", MONEY, nullable=False),
    UniqueConstraint("party_id", "position", name="uq_one_charge_per_position"),
)
"""``(kind, session_id)`` in the key is the rule that makes both event handlers redeliverable.

"A charge is raised **once per ``(kind, session_id)``**. That, and not a de-duplication table
in either handler, is what makes a redelivered ``OfferAccepted`` or ``SessionOpened`` a
no-op." The constraint says the same thing to anybody who reaches the table another way.

``position`` is the order raised, and it is load-bearing rather than cosmetic: allocation is
"the gating charge first, then charges in the order raised", so a transcript of the ledger read
back in a different order would allocate a future payment differently.
"""

payments = Table(
    "payments",
    metadata,
    Column(
        "party_id",
        String,
        ForeignKey(f"{SCHEMA}.accounts.party_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("gateway_ref", String, primary_key=True),
    Column("position", Integer, nullable=False),
    Column("amount", MONEY, nullable=False),
    Column("received_at", DateTime(timezone=True), nullable=False),
)
"""``gateway_ref`` in the primary key is the idempotency invariant, in the schema.

The account already no-ops a duplicate reference, and CLAUDE.md section 6 names that invariant
as escalation-worthy to touch. This is the same rule stated where a second code path could not
get around it.
"""

fee_schedules = Table(
    "fee_schedules",
    metadata,
    Column("session_id", String, primary_key=True),
    Column("acceptance_fee", MONEY, nullable=False),
    Column("matriculation_fee", MONEY, nullable=False),
    Column("ordinal", Integer, Identity(), nullable=False, unique=True),
)
"""Admission fees per session and not per program, exactly as ``FeeSchedule`` argues.

"They are paid once, by an applicant who at that moment has no level and may yet end up on a
program other than the one they applied for... a key nobody populates is worse than no key at
all."
"""

session_fee_lines = Table(
    "session_fee_lines",
    metadata,
    Column(
        "session_id",
        String,
        ForeignKey(f"{SCHEMA}.fee_schedules.session_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("program_id", String, primary_key=True),
    Column("level", Integer, primary_key=True),
    Column("amount", MONEY, nullable=False),
)
"""``(program_id, level)`` in the key is the schedule's own duplicate check.

``FeeSchedule`` refuses a schedule pricing one combination twice, because "whichever the code
picked, half the cohort would be charged the figure nobody meant".
"""

payment_intents = Table(
    "payment_intents",
    metadata,
    Column("reference", String, primary_key=True),
    Column("party_id", String, nullable=False, index=True),
    Column("amount", MONEY, nullable=False),
    Column("confirmed_amount", MONEY, nullable=True),
    Column("initiated_at", DateTime(timezone=True), nullable=False),
    Column("resolved_at", DateTime(timezone=True), nullable=True),
    Column("ttl_seconds", Integer, nullable=False),
    Column("status", String, nullable=False),
    Column("failure_reason", String, nullable=True),
    Column("ordinal", Integer, Identity(), nullable=False, unique=True),
)
"""``amount`` and ``confirmed_amount`` are two columns because they are two facts.

"The first is what was asked for, the second is what the gateway says actually moved", and the
ledger records the second. A short payment confirms the intent and leaves the charge
outstanding, and both are true at once — which a single column could not say.

``ttl_seconds`` rather than a timestamp, because the TTL is a duration the intent was opened
with and ``DEFAULT_INTENT_TTL`` is a construction argument. Storing a computed deadline would
bake a policy that is meant to be changeable into every row already written.
"""
