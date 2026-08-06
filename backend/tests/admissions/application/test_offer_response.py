"""Answering an offer: accepting it, or declining it and giving the place back.

Two use cases, and the interesting thing about them is that they write their two aggregates
in *opposite* orders. Both orderings are chosen the way ``MakeOfferToApplicant._claim``
chooses its own — by which half-finished state the university can live with — and the tests
below assert the surviving state rather than just the happy path, because an ordering nobody
tested is an ordering that has not been decided.

``AcceptOffer`` publishes before it saves: the consumer is idempotent, so a crash after
publication heals on retry. ``DeclineOffer`` saves before it releases: nothing heals a
half-finished decline, so it must fail towards under-admitting rather than over-admitting.
"""

from datetime import date

import pytest

from admissions.adapters.outbound import InMemoryEventBus
from admissions.application import (
    AcceptOffer,
    AcceptOfferCommand,
    AdmissionCycleNotFoundError,
    ApplicantNotFoundError,
    DeclineOffer,
    DeclineOfferCommand,
)
from admissions.domain import (
    AdmissionCycle,
    Applicant,
    ApplicationOutcomeFinalError,
    ApplicationStatus,
    BioData,
    NoOfferToRespondToError,
    OfferAlreadyRespondedToError,
    UtmeResult,
    UtmeSubjectScore,
)
from admissions.domain.events import OfferAccepted
from admissions.ports import AdmissionCycleRepositoryPort, ApplicantRepositoryPort

APPLICANT_ID = "app-0001"
COMPUTER_SCIENCE = "prg-csc"
MATHEMATICS = "prg-mth"
SESSION_ID = "sess-2026"

ACCEPT = AcceptOfferCommand(APPLICANT_ID)
DECLINE = DeclineOfferCommand(APPLICANT_ID)

BIO = BioData("Adaeze Okonkwo", date_of_birth=date(2006, 4, 1), email="adaeze@example.com")
SUBJECTS = ("USE OF ENGLISH", "MATHEMATICS", "PHYSICS", "BIOLOGY")


def an_applicant() -> Applicant:
    return Applicant.apply(
        applicant_id=APPLICANT_ID,
        applied_program_id=COMPUTER_SCIENCE,
        session_id=SESSION_ID,
        bio_data=BIO,
        utme_result=UtmeResult(tuple(UtmeSubjectScore(subject, 70) for subject in SUBJECTS)),
    )


def an_offered_applicant(program_id: str = COMPUTER_SCIENCE) -> Applicant:
    """Screened and holding an offer — the only state either use case will act on."""
    applicant = an_applicant()
    applicant.screen()
    applicant.offer(program_id)
    return applicant


class _RecordingApplicants:
    """A repository that counts its writes, so a test can assert *when* one happened.

    Needed because the in-memory adapter's identity map hands back the very object the use
    case mutated: "did this get saved?" cannot be answered by reading it again, only by
    watching the call.
    """

    def __init__(self, inner: ApplicantRepositoryPort) -> None:
        self._inner = inner
        self.saves = 0

    async def add(self, applicant: Applicant) -> None:
        await self._inner.add(applicant)

    async def get(self, applicant_id: str) -> Applicant | None:
        return await self._inner.get(applicant_id)

    async def save(self, applicant: Applicant) -> None:
        self.saves += 1
        await self._inner.save(applicant)


@pytest.fixture
async def offered(applicants: ApplicantRepositoryPort) -> Applicant:
    applicant = an_offered_applicant()
    await applicants.add(applicant)
    return applicant


@pytest.fixture
async def claimed_cycle(cycles: AdmissionCycleRepositoryPort) -> AdmissionCycle:
    """Computer Science with two places, one of them claimed by the offer above."""
    cycle = AdmissionCycle(COMPUTER_SCIENCE, SESSION_ID, 2, offers_made=1)
    await cycles.add(cycle)
    return cycle


# ---- accepting ----


class TestAcceptOffer:
    async def test_an_accepted_offer_is_recorded_and_announced(
        self,
        accept_offer: AcceptOffer,
        applicants: ApplicantRepositoryPort,
        events: InMemoryEventBus,
        offered: Applicant,
    ) -> None:
        result = await accept_offer.execute(ACCEPT)

        stored = await applicants.get(APPLICANT_ID)
        assert stored is not None
        assert stored.status is ApplicationStatus.ACCEPTED
        assert result.program_id == COMPUTER_SCIENCE
        assert events.published == (
            OfferAccepted(
                applicant_id=APPLICANT_ID, program_id=COMPUTER_SCIENCE, session_id=SESSION_ID
            ),
        )

    async def test_the_announced_program_is_the_offered_one_not_the_applied_one(
        self,
        accept_offer: AcceptOffer,
        applicants: ApplicantRepositoryPort,
        events: InMemoryEventBus,
    ) -> None:
        """An applicant placed on an alternative is billed for where they are going."""
        await applicants.add(an_offered_applicant(MATHEMATICS))

        result = await accept_offer.execute(ACCEPT)

        assert result.program_id == MATHEMATICS
        (published,) = events.published
        assert published.program_id == MATHEMATICS

    async def test_it_publishes_before_it_saves(
        self,
        applicants: ApplicantRepositoryPort,
        offered: Applicant,
    ) -> None:
        """The ordering that lets a crash between the two writes heal on retry.

        Asserted by counting saves at the moment of publication rather than by inspecting the
        repository afterwards: the in-memory adapter holds an identity map, so the aggregate
        it returns *is* the one the use case mutated and would look accepted either way
        (CLAUDE.md section 4). Only the call order distinguishes the two designs.

        Saving first would be the unrecoverable order — ``accept()`` refuses to run twice, so
        a publish that failed afterwards strands somebody accepted forever whose ledger
        nobody can open.
        """
        saves_at_publish: list[int] = []
        recording = _RecordingApplicants(applicants)

        class Watching(InMemoryEventBus):
            async def publish(self, event: object) -> None:  # type: ignore[override]
                saves_at_publish.append(recording.saves)

        await AcceptOffer(recording, Watching()).execute(ACCEPT)  # type: ignore[arg-type]

        assert saves_at_publish == [0]
        assert recording.saves == 1

    async def test_a_failed_publication_leaves_the_applicant_unsaved(
        self,
        applicants: ApplicantRepositoryPort,
        offered: Applicant,
    ) -> None:
        """The consequence of that ordering: the write that cannot be repeated never happened."""
        recording = _RecordingApplicants(applicants)

        class Failing(InMemoryEventBus):
            async def publish(self, event: object) -> None:  # type: ignore[override]
                raise RuntimeError("bus down")

        with pytest.raises(RuntimeError, match="bus down"):
            await AcceptOffer(recording, Failing()).execute(ACCEPT)  # type: ignore[arg-type]

        assert recording.saves == 0

    async def test_an_unknown_applicant_is_an_error(self, accept_offer: AcceptOffer) -> None:
        with pytest.raises(ApplicantNotFoundError, match=APPLICANT_ID):
            await accept_offer.execute(ACCEPT)

    async def test_accepting_twice_is_refused(
        self, accept_offer: AcceptOffer, offered: Applicant
    ) -> None:
        await accept_offer.execute(ACCEPT)
        with pytest.raises(OfferAlreadyRespondedToError):
            await accept_offer.execute(ACCEPT)

    async def test_an_applicant_holding_no_offer_is_refused(
        self, accept_offer: AcceptOffer, applicants: ApplicantRepositoryPort
    ) -> None:
        await applicants.add(an_applicant())
        with pytest.raises(NoOfferToRespondToError):
            await accept_offer.execute(ACCEPT)


# ---- declining ----


class TestDeclineOffer:
    async def test_a_declined_offer_returns_its_place_to_the_quota(
        self,
        decline_offer: DeclineOffer,
        applicants: ApplicantRepositoryPort,
        cycles: AdmissionCycleRepositoryPort,
        offered: Applicant,
        claimed_cycle: AdmissionCycle,
    ) -> None:
        """The decision this phase settled: a place let go is a place a real candidate can have."""
        result = await decline_offer.execute(DECLINE)

        stored_applicant = await applicants.get(APPLICANT_ID)
        stored_cycle = await cycles.get(COMPUTER_SCIENCE, SESSION_ID)
        assert stored_applicant is not None
        assert stored_cycle is not None
        assert stored_applicant.status is ApplicationStatus.DECLINED
        assert stored_cycle.offers_made == 0
        assert result.places_remaining == 2

    async def test_it_releases_the_offered_program_s_cycle(
        self,
        decline_offer: DeclineOffer,
        cycles: AdmissionCycleRepositoryPort,
        applicants: ApplicantRepositoryPort,
    ) -> None:
        """An alternative offer claimed its place on the alternative's cycle, not the applied
        program's — so that is the cycle the refusal gives it back to."""
        await applicants.add(an_offered_applicant(MATHEMATICS))
        await cycles.add(AdmissionCycle(COMPUTER_SCIENCE, SESSION_ID, 1, offers_made=1))
        await cycles.add(AdmissionCycle(MATHEMATICS, SESSION_ID, 1, offers_made=1))

        await decline_offer.execute(DECLINE)

        applied = await cycles.get(COMPUTER_SCIENCE, SESSION_ID)
        alternative = await cycles.get(MATHEMATICS, SESSION_ID)
        assert applied is not None and alternative is not None
        assert (applied.offers_made, alternative.offers_made) == (1, 0)

    async def test_it_saves_the_applicant_before_it_releases_the_place(
        self,
        decline_offer: DeclineOffer,
        applicants: ApplicantRepositoryPort,
        offered: Applicant,
    ) -> None:
        """No cycle stored, so the release fails. The refusal must still stand.

        The surviving state is "declined, place not returned" — the program under-admits by
        one and an administrator can correct it. The opposite order would free a place while
        the applicant could still accept, and the program would over-admit.
        """
        with pytest.raises(AdmissionCycleNotFoundError, match=COMPUTER_SCIENCE):
            await decline_offer.execute(DECLINE)

        stored = await applicants.get(APPLICANT_ID)
        assert stored is not None
        assert stored.status is ApplicationStatus.DECLINED

    async def test_declining_twice_is_refused_before_the_cycle_is_touched(
        self,
        decline_offer: DeclineOffer,
        cycles: AdmissionCycleRepositoryPort,
        offered: Applicant,
        claimed_cycle: AdmissionCycle,
    ) -> None:
        """Double-release is impossible without a guard, because ``DECLINED`` is terminal —
        and being terminal is why the second attempt raises ``ApplicationOutcomeFinalError``
        rather than the "already responded" error an accepted applicant would get."""
        await decline_offer.execute(DECLINE)
        with pytest.raises(ApplicationOutcomeFinalError):
            await decline_offer.execute(DECLINE)

        stored = await cycles.get(COMPUTER_SCIENCE, SESSION_ID)
        assert stored is not None
        assert stored.offers_made == 0

    async def test_declining_publishes_nothing(
        self,
        decline_offer: DeclineOffer,
        events: InMemoryEventBus,
        offered: Applicant,
        claimed_cycle: AdmissionCycle,
    ) -> None:
        """No context was ever told the offer existed, so none needs telling it is over."""
        await decline_offer.execute(DECLINE)
        assert events.published == ()

    async def test_an_unknown_applicant_is_an_error(self, decline_offer: DeclineOffer) -> None:
        with pytest.raises(ApplicantNotFoundError, match=APPLICANT_ID):
            await decline_offer.execute(DECLINE)

    async def test_an_applicant_holding_no_offer_is_refused(
        self, decline_offer: DeclineOffer, applicants: ApplicantRepositoryPort
    ) -> None:
        await applicants.add(an_applicant())
        with pytest.raises(NoOfferToRespondToError):
            await decline_offer.execute(DECLINE)
