"""Domain events published by the Billing context.

Past-tense facts, immutable once produced. Consumers never import these classes; an outbound
adapter serialises them at the boundary — the same contract Faculty & Department states for
its own events, and the reason a bus carries a name and a mapping rather than a type.

One event, and its shape is dictated by its consumer. CLAUDE.md section 3 says Admissions
"Consumes ``AcceptanceFeePaid(applicant_id)``", so the field is ``applicant_id`` and not
``party_id``, even though this context knows the value as a party-id. Over there the fact
means "this applicant may now be matriculated", and naming the field after the party
abstraction would make a consumer translate a concept it has no use for.

What the event does *not* carry is an instruction. It does not say to matriculate anybody:
matriculation is a human-triggered use case that checks a flag (CLAUDE.md section 3), and
"Do not auto-matriculate on payment" is in the list of things not to do. It also carries no
amount and no gateway reference — how much was paid and by what route is this ledger's
business, and a consumer holding either would eventually make a decision on it.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AcceptanceFeePaid:
    """The gating acceptance charge on an account has been settled in full.

    Published exactly once per party, because settlement is monotonic: a charge that has
    absorbed everything it is owed can never become outstanding again, so the transition that
    produces this fact happens once and cannot be re-entered.
    """

    applicant_id: str


DomainEvent = AcceptanceFeePaid
"""Every fact this context publishes. The event publisher port speaks in this type.

A single member today rather than a union of several. When Phase 5.3's payment intents add
facts worth announcing, this becomes ``A | B`` and nothing above it changes shape.
"""
