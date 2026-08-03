"""Find a screened applicant a place: their program if it has one, an alternative if not."""

from dataclasses import dataclass

from admissions.application.errors import AdmissionCycleNotFoundError, ApplicantNotFoundError
from admissions.domain.admission_cycle import AdmissionCycle
from admissions.domain.applicant import Applicant
from admissions.domain.outcomes import OfferRecorded
from admissions.domain.subject_combination_rule import SubjectCombinationRule
from admissions.ports.admission_cycle_repository import AdmissionCycleRepositoryPort
from admissions.ports.alternative_program_policy_repository import (
    AlternativeProgramPolicyRepositoryPort,
)
from admissions.ports.applicant_repository import ApplicantRepositoryPort
from admissions.ports.entry_requirement_repository import ProgramEntryRequirementRepositoryPort


@dataclass(frozen=True)
class MakeOfferToApplicantCommand:
    """An identifier only: everything the decision turns on is looked up, not passed in.

    Nothing here says which program to offer. If a caller could name one, a caller could
    name one with no places left, and the quota invariant would be enforced against
    whatever the caller happened to believe.
    """

    applicant_id: str


@dataclass(frozen=True)
class OfferMade:
    """A place was claimed and the applicant holds it.

    Both program ids, because a letter has to say both: what was asked for and what is
    being offered. An applicant reading that they have a place on Mathematics when they
    applied for Computer Science needs the sentence to contain the word Computer Science.
    """

    applicant_id: str
    program_id: str
    applied_program_id: str

    @property
    def is_alternative(self) -> bool:
        """Whether this was a fallback rather than the program applied for.

        Derived, never stored, in the manner of ``UtmeResult.aggregate``: it is a
        comparison of two fields already here, and holding it separately would be a third
        field that could disagree with them.
        """
        return self.program_id != self.applied_program_id


@dataclass(frozen=True)
class NoOfferAvailable:
    """Every program that could have taken the applicant was full or would not have them.

    ``considered`` names each program the flow examined, in the order it examined them:
    the applied program first, then the fallback chain. It is what lets somebody answer
    "was I even looked at for Mathematics?" without re-running the decision against policy
    that may since have changed.
    """

    applicant_id: str
    applied_program_id: str
    considered: tuple[str, ...]


OfferDecision = OfferMade | NoOfferAvailable
"""Both ways the offer flow can end. Neither is an exception; callers handle both.

Not to be confused with ``OfferOutcome``, which is what a single ``AdmissionCycle`` answers
about a single program. This is what the whole flow answers about an applicant, and one of
these is the conclusion of anywhere between one and many of those.
"""


class MakeOfferToApplicant:
    """Offer a screened applicant a place, trying alternatives when their program is full.

    The order is CLAUDE.md section 3's, and it is entirely orchestration: try the applied
    program's cycle; on ``QuotaExhausted`` walk the ``AlternativeProgramPolicy``, filtered
    by ``SubjectCombinationRule``; the first qualifying program with room takes them;
    otherwise the application closes with no offer available. Not one of those judgements
    is made here — the cycle decides whether there is a place, the rule decides whether the
    applicant qualifies, the aggregate decides whether it may be offered anything at all.
    This class decides only *what to ask next*, which is the one thing no aggregate can
    know, because knowing it would mean holding another aggregate's state.

    Fully automatic: nobody chooses the alternative. The choice was made when the faculty
    wrote the fallback chain down, and an admissions officer picking from it by hand is
    exactly the discretion the policy exists to remove.

    **No transaction spans two aggregates** (CLAUDE.md section 4). A place is claimed on a
    cycle and saved; only then does the applicant record that they hold it. The two writes
    are sequential and separate, and the failure between them is a real one — see
    :meth:`_claim` for which way round it is allowed to fail and why.
    """

    def __init__(
        self,
        applicants: ApplicantRepositoryPort,
        cycles: AdmissionCycleRepositoryPort,
        requirements: ProgramEntryRequirementRepositoryPort,
        policies: AlternativeProgramPolicyRepositoryPort,
        rule: SubjectCombinationRule | None = None,
    ) -> None:
        self._applicants = applicants
        self._cycles = cycles
        self._requirements = requirements
        self._policies = policies
        self._rule = rule or SubjectCombinationRule()

    async def execute(self, command: MakeOfferToApplicantCommand) -> OfferDecision:
        """Decide the applicant's place and record it.

        Returns:
            OfferMade: a place was claimed, on the applied program or an alternative.
            NoOfferAvailable: nothing was left anywhere the applicant could go; the
                application is now ``NO_OFFER_AVAILABLE`` and final.

        Raises:
            ApplicantNotFoundError: no application is stored under that id.
            AdmissionCycleNotFoundError: no cycle was opened for the applied program.
            ApplicantNotScreenedError: the applicant has not been screened yet.
            OfferAlreadyMadeError: the application has already been decided.
            ApplicationOutcomeFinalError: the application already reached an outcome.
        """
        applicant = await self._applicants.get(command.applicant_id)
        if applicant is None:
            raise ApplicantNotFoundError(f"no applicant stored with id {command.applicant_id!r}")

        # Asked before any cycle is: claiming a place is a write to another aggregate, and
        # a place claimed for somebody who may not be offered one has nowhere to go back to.
        applicant.require_awaiting_decision()

        applied_program_id = applicant.applied_program_id
        cycle = await self._cycles.get(applied_program_id, applicant.session_id)
        if cycle is None:
            raise AdmissionCycleNotFoundError(
                f"no admission cycle is open for program {applied_program_id!r} "
                f"in session {applicant.session_id!r}"
            )

        considered = [applied_program_id]
        if isinstance(cycle.offer(), OfferRecorded):
            await self._claim(applicant, cycle)
            return OfferMade(
                applicant_id=applicant.applicant_id,
                program_id=applied_program_id,
                applied_program_id=applied_program_id,
            )

        # The applied program is full. Nothing was claimed and nothing changed on that
        # cycle, so it is not saved: a QuotaExhausted cycle is the cycle we already had.
        for alternative in await self._alternatives_for(applicant):
            considered.append(alternative)
            alternative_cycle = await self._offerable(applicant, alternative)
            if alternative_cycle is not None:
                await self._claim(applicant, alternative_cycle)
                return OfferMade(
                    applicant_id=applicant.applicant_id,
                    program_id=alternative,
                    applied_program_id=applied_program_id,
                )

        applicant.record_no_offer()
        await self._applicants.save(applicant)
        return NoOfferAvailable(
            applicant_id=applicant.applicant_id,
            applied_program_id=applied_program_id,
            considered=tuple(considered),
        )

    async def _alternatives_for(self, applicant: Applicant) -> tuple[str, ...]:
        """The fallback chain for the program applied for, or none.

        A program with no published policy has no fallback, exactly like one with an empty
        chain. The two are deliberately the same answer here: neither says anything is
        wrong, only that this program overflows nowhere.
        """
        policy = await self._policies.get(applicant.applied_program_id, applicant.session_id)
        return () if policy is None else policy.alternatives

    async def _offerable(self, applicant: Applicant, program_id: str) -> AdmissionCycle | None:
        """Return the alternative's cycle with a place claimed on it, or ``None`` to move on.

        Four ways an alternative drops out, and none of them is an error — the chain is a
        list of possibilities, and a possibility that did not work out is the ordinary
        case:

        * nobody published an entry requirement for it this session;
        * the applicant's subjects do not qualify them for it;
        * nobody opened a cycle for it this session;
        * its cycle is full.

        The first and third are missing data rather than decisions, and are still passed
        over rather than raised. A program named in a fallback chain but not actually run
        this session is a normal thing for a chain written before the session opened to
        contain, and turning that into an error would deny a place to an applicant whose
        *next* alternative had room.

        Qualification is checked before the cycle is asked, which is both the order
        CLAUDE.md section 3 states and the only order that is safe: asking first would
        claim a place for somebody who turns out not to qualify for it, and there is no
        way to give it back.
        """
        requirement = await self._requirements.get(program_id, applicant.session_id)
        if requirement is None:
            return None
        if not self._rule.qualifies(requirement, applicant.utme_result):
            return None

        cycle = await self._cycles.get(program_id, applicant.session_id)
        if cycle is None:
            return None
        if not isinstance(cycle.offer(), OfferRecorded):
            return None
        return cycle

    async def _claim(self, applicant: Applicant, cycle: AdmissionCycle) -> None:
        """Persist the claimed place, then the applicant holding it. Two transactions.

        The order is deliberate, and it is chosen by which failure the university can live
        with. A crash between the two writes leaves the cycle a place short with nobody
        holding it: the program under-admits by one, an administrator can see it and hand
        the place out. The other order would leave an applicant holding an offer against a
        place that was never reserved, and a program that over-admits has broken the
        invariant ``AdmissionCycle`` exists for — by the time anyone notices, the extra
        student has a matric number.

        That the applicant can be offered anything at all was established at the top of
        :meth:`execute`, before a place was claimed anywhere. The aggregate makes the check
        again here, and is right to.
        """
        await self._cycles.save(cycle)
        applicant.offer(cycle.program_id)
        await self._applicants.save(applicant)
