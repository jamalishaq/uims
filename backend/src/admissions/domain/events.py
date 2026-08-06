"""Domain events published by the Admissions context.

Past-tense facts, immutable once produced. Consumers never import these classes; an
outbound adapter serialises them at the boundary. Both consumers written against these
facts already say so in their own words — Billing's ``OfferAcceptedHandler`` and Student
Profile's ``StudentMatriculatedHandler`` each declare their own message type and translate,
because "a consumer never imports a publisher's event type" (CLAUDE.md section 3).

**Two facts, and deliberately not five.** CLAUDE.md section 3 names exactly these two, and
each transition that announces nothing is worth stating:

* An offer being **made** is not published. Nothing downstream reacts to it: no ledger is
  opened, no student exists, and the applicant has not yet done anything. An offer is a
  question, and only the answer is a fact anybody else needs.
* An offer being **declined** is not published. The place it frees goes back to the cycle
  the same use case is already holding — see ``DeclineOffer`` — and no other context has
  ever been told the offer existed.
* An application closing with **no offer available** is not published. It is the absence of
  a place, and nobody is waiting to hear about one that was never given.
* The acceptance fee **clearing** is not published from here. It arrives *at* this context
  from Billing, and this context's reaction is a flag on an aggregate.

Writing an event nobody consumes would be inventing a wire format that can be neither right
nor wrong, which is the argument ``src/main.py`` made for refusing to guess these two before
a publisher existed. Now there is one, and the two shapes below are the ones the two waiting
handlers were already written against.
"""

from dataclasses import dataclass

from admissions.domain.values import BioData


@dataclass(frozen=True)
class OfferAccepted:
    """An applicant took up their offer. Billing opens their ledger on this.

    ``program_id`` is the **offered** program, never the applied one. An applicant placed on
    an alternative is billed for where they are going, and every downstream context means the
    offered program when it says "their program" — which is the whole reason ``Applicant``
    carries two program ids.

    No level and no amount: Admissions has an opinion about neither. Billing's own
    ``ENTRY_LEVEL`` fills the first and its ``FeeSchedule`` prices the second, which is why
    ``OfferAcceptedMessage`` defaults ``level`` rather than requiring it of us.
    """

    applicant_id: str
    program_id: str
    session_id: str


@dataclass(frozen=True)
class StudentMatriculated:
    """An accepted, fee-cleared applicant became a student. Student Profile creates one.

    ``bio_data`` crosses whole rather than pre-flattened, in the manner of ``SessionOpened``
    carrying an ``AcademicYear``: the bus serialises with :func:`dataclasses.asdict`, so what
    a subscriber receives is nested primitives and never this context's value object. The
    consuming adapter flattens it into its own ``StudentMatriculatedMessage``, which is
    exactly the translation an anti-corruption layer is for.

    **No matric number**, and CLAUDE.md section 3 says why: issuing one is Student Profile's
    job, and an event carrying it would mean Admissions had already done that job. Nothing
    is published back either — a matric number is not needed at acceptance-letter time, so
    this context is never told what was issued.

    **No student id.** That identifier is Student Profile's to mint; Admissions has no
    business naming another context's aggregate.
    """

    applicant_id: str
    program_id: str
    session_id: str
    bio_data: BioData


DomainEvent = OfferAccepted | StudentMatriculated
"""Every fact this context publishes. The event publisher port speaks in this type."""
