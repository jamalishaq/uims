"""The registrar's dashboard for one program: the quota, and the funnel underneath it.

**Two populations, and confusing them is the thing this module exists to prevent.**

``offers_made`` on the ``AdmissionCycle`` counts places claimed *on this program* — including
places claimed by applicants who applied somewhere else and overflowed here through another
program's fallback chain. The funnel counts applicants who *applied to* this program —
including ones who ended up offered a place somewhere else entirely.

They are different sets and they will not add up, which is correct rather than a defect. A
registrar looking at Computer Science needs both: "how many of my places are gone" is a
capacity question, and "what happened to the people who wanted to come here" is a cohort
question. Reporting one and calling it the other is how a department discovers in September
that it admitted forty people it never saw.

**The funnel is reported as counts per status rather than as one number**, because a single
"applicants" figure hides exactly the gap the registrar's job lives in — the people who are
screened and waiting on a decision.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from admissions.domain.applicant import Applicant, ApplicationStatus
from admissions.ports.admission_cycle_repository import AdmissionCycleRepositoryPort
from admissions.ports.applicant_repository import ApplicantRepositoryPort


@dataclass(frozen=True)
class SummariseProgramAdmissionsCommand:
    """Which program's intake to summarise, for which session."""

    program_id: str
    session_id: str


@dataclass(frozen=True)
class ProgramAdmissionsSummary:
    """One program's capacity and one program's cohort, side by side.

    ``quota``, ``offers_made``, ``places_remaining`` and ``is_full`` are ``None`` when no cycle
    was opened. That is a real and common state — a registrar who has published a requirement
    but not yet set a quota — and reporting it as zero would say the program is full.

    The status counts are over applicants whose *applied* program is this one. See the module
    docstring on why they do not reconcile with ``offers_made``.
    """

    program_id: str
    session_id: str
    quota: int | None
    offers_made: int | None
    places_remaining: int | None
    is_full: bool | None
    applied: int
    screened: int
    offered: int
    accepted: int
    declined: int
    matriculated: int
    no_offer_available: int
    total_applicants: int


class SummariseProgramAdmissions:
    """Read a program's quota and the state of everyone who applied to it."""

    def __init__(
        self,
        applicants: ApplicantRepositoryPort,
        cycles: AdmissionCycleRepositoryPort,
    ) -> None:
        self._applicants = applicants
        self._cycles = cycles

    async def execute(self, command: SummariseProgramAdmissionsCommand) -> ProgramAdmissionsSummary:
        """Summarise, reading the cohort through the session and filtering in memory.

        ``list_for_session`` is the only list query Admissions has, and filtering by applied
        program here rather than adding a repository method is deliberate for now: a session's
        applicants is the natural page of this data, and a second query keyed by program would
        be a second index to keep true. If a cohort ever outgrows that, the port grows a
        method — the use case's shape does not change.
        """
        cohort = _for_applied_program(
            await self._applicants.list_for_session(command.session_id), command.program_id
        )
        counts = _counts(cohort)
        cycle = await self._cycles.get(command.program_id, command.session_id)

        return ProgramAdmissionsSummary(
            program_id=command.program_id,
            session_id=command.session_id,
            quota=cycle.quota if cycle else None,
            offers_made=cycle.offers_made if cycle else None,
            places_remaining=cycle.places_remaining if cycle else None,
            is_full=cycle.is_full if cycle else None,
            applied=counts[ApplicationStatus.APPLIED],
            screened=counts[ApplicationStatus.SCREENED],
            offered=counts[ApplicationStatus.OFFERED],
            accepted=counts[ApplicationStatus.ACCEPTED],
            declined=counts[ApplicationStatus.DECLINED],
            matriculated=counts[ApplicationStatus.MATRICULATED],
            no_offer_available=counts[ApplicationStatus.NO_OFFER_AVAILABLE],
            total_applicants=len(cohort),
        )


def _for_applied_program(applicants: Iterable[Applicant], program_id: str) -> tuple[Applicant, ...]:
    """Everyone who *applied* to this program, whatever they were eventually offered."""
    return tuple(
        applicant for applicant in applicants if applicant.applied_program_id == program_id
    )


def _counts(applicants: Iterable[Applicant]) -> dict[ApplicationStatus, int]:
    """Every status keyed, including the ones nobody is in — a missing key is not a zero."""
    counts = dict.fromkeys(ApplicationStatus, 0)
    for applicant in applicants:
        counts[applicant.status] += 1
    return counts
