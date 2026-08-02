"""The alternative-offer flow: the architecture's real test, run end to end.

This is the multi-aggregate flow CLAUDE.md section 4 forbids putting in one transaction,
and every test here is really about the same question — did the orchestration touch
exactly the aggregates it was entitled to touch, and no others? The assertions that look
redundant carry that weight: after an alternative offer, the *first* alternative's cycle
must still read zero, because a place claimed on a program the applicant was never offered
is a place lost to a real candidate and nothing downstream would ever notice.

The four scenarios the build playbook asks for lead: a direct offer; an alternative offer
where the first alternative is unqualified and the second succeeds; every alternative full
giving no offer available; and ``offered_program_id`` differing from
``applied_program_id``. The rest are the edges those four run past.

A LASU-shaped cast throughout. Computer Science, Mathematics and Statistics all demand Use
of English, Mathematics and Physics plus one of Chemistry/Biology/Geography. Physics
demands Chemistry outright, and our applicant sat Biology — which is what makes Physics the
alternative they do not qualify for.
"""

from datetime import date

import pytest

from admissions.application import (
    AdmissionCycleNotFoundError,
    ApplicantNotFoundError,
    MakeOfferToApplicant,
    MakeOfferToApplicantCommand,
    NoOfferAvailable,
    OfferMade,
)
from admissions.domain import (
    AdmissionCycle,
    AlternativeProgramPolicy,
    Applicant,
    ApplicantNotScreenedError,
    ApplicationOutcomeFinalError,
    ApplicationStatus,
    BioData,
    OfferAlreadyMadeError,
    ProgramEntryRequirement,
    SubjectGroup,
    UtmeResult,
    UtmeSubjectScore,
)
from admissions.ports import (
    AdmissionCycleRepositoryPort,
    AlternativeProgramPolicyRepositoryPort,
    ApplicantRepositoryPort,
    ProgramEntryRequirementRepositoryPort,
)

APPLICANT_ID = "app-0001"
COMPUTER_SCIENCE = "prg-csc"
MATHEMATICS = "prg-mth"
STATISTICS = "prg-sta"
PHYSICS = "prg-phy"
SESSION_ID = "sess-2026"
OTHER_SESSION_ID = "sess-2027"

COMMAND = MakeOfferToApplicantCommand(APPLICANT_ID)

BIO = BioData("Adaeze Okonkwo", date_of_birth=date(2006, 4, 1), email="adaeze@example.com")

CORE_SCIENCE_SUBJECTS = ("USE OF ENGLISH", "MATHEMATICS", "PHYSICS")
QUALIFYING_SUBJECTS = (*CORE_SCIENCE_SUBJECTS, "BIOLOGY")
"""Meets Computer Science, Mathematics and Statistics. Not Physics, which wants Chemistry."""


def a_screened_applicant(subjects: tuple[str, ...] = QUALIFYING_SUBJECTS) -> Applicant:
    applicant = Applicant.apply(
        applicant_id=APPLICANT_ID,
        applied_program_id=COMPUTER_SCIENCE,
        session_id=SESSION_ID,
        bio_data=BIO,
        utme_result=UtmeResult(tuple(UtmeSubjectScore(subject, 70) for subject in subjects)),
    )
    applicant.screen()
    return applicant


def a_cycle(
    program_id: str, quota: int = 1, *, offers_made: int = 0, session_id: str = SESSION_ID
) -> AdmissionCycle:
    return AdmissionCycle(program_id, session_id, quota, offers_made=offers_made)


def a_full_cycle(program_id: str) -> AdmissionCycle:
    """A cycle with its one place already claimed. ``offer()`` on this says QuotaExhausted."""
    return a_cycle(program_id, 1, offers_made=1)


def a_science_requirement(program_id: str, session_id: str = SESSION_ID) -> ProgramEntryRequirement:
    """Use of English, Mathematics and Physics, plus a choice for the fourth."""
    return ProgramEntryRequirement.for_program(
        program_id,
        session_id,
        required_subjects=CORE_SCIENCE_SUBJECTS,
        one_of_groups=(SubjectGroup(frozenset({"CHEMISTRY", "BIOLOGY", "GEOGRAPHY"})),),
    )


def a_chemistry_requirement(program_id: str) -> ProgramEntryRequirement:
    """Demands Chemistry outright. Our applicant sat Biology, so this one turns them away."""
    return ProgramEntryRequirement.for_program(
        program_id,
        SESSION_ID,
        required_subjects=(*CORE_SCIENCE_SUBJECTS, "CHEMISTRY"),
    )


def a_policy(
    alternatives: tuple[str, ...], session_id: str = SESSION_ID
) -> AlternativeProgramPolicy:
    return AlternativeProgramPolicy.for_program(COMPUTER_SCIENCE, session_id, alternatives)


def offers_made_on(cycles: AdmissionCycleRepositoryPort, program_id: str) -> int:
    cycle = cycles.get(program_id, SESSION_ID)
    assert cycle is not None, f"no cycle stored for {program_id}"
    return cycle.offers_made


def stored(applicants: ApplicantRepositoryPort) -> Applicant:
    applicant = applicants.get(APPLICANT_ID)
    assert applicant is not None
    return applicant


@pytest.fixture
def screened_application(applicants: ApplicantRepositoryPort) -> None:
    applicants.add(a_screened_applicant())


@pytest.fixture
def overflow_chain(
    requirements: ProgramEntryRequirementRepositoryPort,
    policies: AlternativeProgramPolicyRepositoryPort,
) -> None:
    """Computer Science overflows into Physics, then Mathematics.

    Physics comes first and the applicant does not qualify for it, which is the whole
    point: the flow has to step past a qualification failure and land on Mathematics.
    """
    requirements.add(a_chemistry_requirement(PHYSICS))
    requirements.add(a_science_requirement(MATHEMATICS))
    policies.add(a_policy((PHYSICS, MATHEMATICS)))


@pytest.mark.usefixtures("screened_application")
class TestAnOfferOnTheProgramAppliedFor:
    def test_the_applicant_is_offered_the_program_they_asked_for(
        self, make_offer_to_applicant: MakeOfferToApplicant, cycles: AdmissionCycleRepositoryPort
    ) -> None:
        cycles.add(a_cycle(COMPUTER_SCIENCE))

        decision = make_offer_to_applicant.execute(COMMAND)

        assert decision == OfferMade(
            applicant_id=APPLICANT_ID,
            program_id=COMPUTER_SCIENCE,
            applied_program_id=COMPUTER_SCIENCE,
        )

    def test_a_direct_offer_is_not_an_alternative_one(
        self, make_offer_to_applicant: MakeOfferToApplicant, cycles: AdmissionCycleRepositoryPort
    ) -> None:
        cycles.add(a_cycle(COMPUTER_SCIENCE))

        decision = make_offer_to_applicant.execute(COMMAND)

        assert isinstance(decision, OfferMade)
        assert decision.is_alternative is False

    def test_the_applicant_now_holds_an_offer_on_that_program(
        self,
        make_offer_to_applicant: MakeOfferToApplicant,
        applicants: ApplicantRepositoryPort,
        cycles: AdmissionCycleRepositoryPort,
    ) -> None:
        cycles.add(a_cycle(COMPUTER_SCIENCE))

        make_offer_to_applicant.execute(COMMAND)

        applicant = stored(applicants)
        assert applicant.status is ApplicationStatus.OFFERED
        assert applicant.offered_program_id == COMPUTER_SCIENCE

    def test_the_claimed_place_is_persisted_on_the_cycle(
        self,
        make_offer_to_applicant: MakeOfferToApplicant,
        cycles: AdmissionCycleRepositoryPort,
    ) -> None:
        """The count has to survive the use case, or the next applicant gets the same place."""
        cycles.add(a_cycle(COMPUTER_SCIENCE, quota=5))

        make_offer_to_applicant.execute(COMMAND)

        assert offers_made_on(cycles, COMPUTER_SCIENCE) == 1

    def test_the_alternatives_are_never_consulted_when_the_program_has_room(
        self,
        make_offer_to_applicant: MakeOfferToApplicant,
        cycles: AdmissionCycleRepositoryPort,
        requirements: ProgramEntryRequirementRepositoryPort,
        policies: AlternativeProgramPolicyRepositoryPort,
    ) -> None:
        cycles.add(a_cycle(COMPUTER_SCIENCE))
        cycles.add(a_cycle(MATHEMATICS))
        requirements.add(a_science_requirement(MATHEMATICS))
        policies.add(a_policy((MATHEMATICS,)))

        make_offer_to_applicant.execute(COMMAND)

        assert offers_made_on(cycles, MATHEMATICS) == 0

    def test_the_last_place_can_be_claimed(
        self, make_offer_to_applicant: MakeOfferToApplicant, cycles: AdmissionCycleRepositoryPort
    ) -> None:
        """Quota boundary from the outside: offers_made == quota - 1 still has one to give."""
        cycles.add(a_cycle(COMPUTER_SCIENCE, quota=3, offers_made=2))

        decision = make_offer_to_applicant.execute(COMMAND)

        assert isinstance(decision, OfferMade)
        assert offers_made_on(cycles, COMPUTER_SCIENCE) == 3


@pytest.mark.usefixtures("screened_application", "overflow_chain")
class TestAnOfferOnAnAlternativeProgram:
    """The headline scenario: first alternative unqualified, second one takes them."""

    def test_the_second_alternative_gets_the_applicant(
        self, make_offer_to_applicant: MakeOfferToApplicant, cycles: AdmissionCycleRepositoryPort
    ) -> None:
        cycles.add(a_full_cycle(COMPUTER_SCIENCE))
        cycles.add(a_cycle(PHYSICS))
        cycles.add(a_cycle(MATHEMATICS))

        decision = make_offer_to_applicant.execute(COMMAND)

        assert decision == OfferMade(
            applicant_id=APPLICANT_ID,
            program_id=MATHEMATICS,
            applied_program_id=COMPUTER_SCIENCE,
        )

    def test_the_offered_program_differs_from_the_applied_one(
        self,
        make_offer_to_applicant: MakeOfferToApplicant,
        applicants: ApplicantRepositoryPort,
        cycles: AdmissionCycleRepositoryPort,
    ) -> None:
        """Two program ids, not one: what they asked for survives what they were offered."""
        cycles.add(a_full_cycle(COMPUTER_SCIENCE))
        cycles.add(a_cycle(PHYSICS))
        cycles.add(a_cycle(MATHEMATICS))

        decision = make_offer_to_applicant.execute(COMMAND)

        applicant = stored(applicants)
        assert applicant.offered_program_id == MATHEMATICS
        assert applicant.applied_program_id == COMPUTER_SCIENCE
        assert applicant.offered_program_id != applicant.applied_program_id
        assert isinstance(decision, OfferMade)
        assert decision.is_alternative is True

    def test_no_place_is_claimed_on_the_alternative_they_did_not_qualify_for(
        self, make_offer_to_applicant: MakeOfferToApplicant, cycles: AdmissionCycleRepositoryPort
    ) -> None:
        """A place claimed for somebody never offered it is a place lost to a real candidate."""
        cycles.add(a_full_cycle(COMPUTER_SCIENCE))
        cycles.add(a_cycle(PHYSICS))
        cycles.add(a_cycle(MATHEMATICS))

        make_offer_to_applicant.execute(COMMAND)

        assert offers_made_on(cycles, PHYSICS) == 0
        assert offers_made_on(cycles, MATHEMATICS) == 1

    def test_the_full_program_is_left_exactly_as_it_was(
        self, make_offer_to_applicant: MakeOfferToApplicant, cycles: AdmissionCycleRepositoryPort
    ) -> None:
        """QuotaExhausted claims nothing: a full cycle does not become fuller."""
        cycles.add(a_cycle(COMPUTER_SCIENCE, quota=2, offers_made=2))
        cycles.add(a_cycle(PHYSICS))
        cycles.add(a_cycle(MATHEMATICS))

        make_offer_to_applicant.execute(COMMAND)

        assert offers_made_on(cycles, COMPUTER_SCIENCE) == 2

    def test_a_full_first_alternative_is_stepped_past_too(
        self,
        make_offer_to_applicant: MakeOfferToApplicant,
        cycles: AdmissionCycleRepositoryPort,
        requirements: ProgramEntryRequirementRepositoryPort,
        policies: AlternativeProgramPolicyRepositoryPort,
    ) -> None:
        """Qualifying is not enough; the chain walks on until something has a place left."""
        cycles.add(a_full_cycle(COMPUTER_SCIENCE))
        cycles.add(a_full_cycle(MATHEMATICS))
        cycles.add(a_cycle(STATISTICS))
        requirements.add(a_science_requirement(STATISTICS))
        policies.save(a_policy((MATHEMATICS, STATISTICS)))

        decision = make_offer_to_applicant.execute(COMMAND)

        assert isinstance(decision, OfferMade)
        assert decision.program_id == STATISTICS

    def test_an_alternative_with_no_published_requirement_is_skipped(
        self,
        make_offer_to_applicant: MakeOfferToApplicant,
        cycles: AdmissionCycleRepositoryPort,
        policies: AlternativeProgramPolicyRepositoryPort,
    ) -> None:
        """Not an error: a chain written before the session opened may name a program
        nobody got round to publishing a requirement for, and raising would deny a place
        the *next* alternative had free."""
        cycles.add(a_full_cycle(COMPUTER_SCIENCE))
        cycles.add(a_cycle(STATISTICS))
        cycles.add(a_cycle(MATHEMATICS))
        policies.save(a_policy((STATISTICS, MATHEMATICS)))

        decision = make_offer_to_applicant.execute(COMMAND)

        assert isinstance(decision, OfferMade)
        assert decision.program_id == MATHEMATICS
        assert offers_made_on(cycles, STATISTICS) == 0

    def test_an_alternative_with_no_open_cycle_is_skipped(
        self,
        make_offer_to_applicant: MakeOfferToApplicant,
        cycles: AdmissionCycleRepositoryPort,
        requirements: ProgramEntryRequirementRepositoryPort,
        policies: AlternativeProgramPolicyRepositoryPort,
    ) -> None:
        """A program named in a chain but not actually run this session is a normal thing."""
        cycles.add(a_full_cycle(COMPUTER_SCIENCE))
        cycles.add(a_cycle(MATHEMATICS))
        requirements.add(a_science_requirement(STATISTICS))
        policies.save(a_policy((STATISTICS, MATHEMATICS)))

        decision = make_offer_to_applicant.execute(COMMAND)

        assert isinstance(decision, OfferMade)
        assert decision.program_id == MATHEMATICS


@pytest.mark.usefixtures("screened_application")
class TestWhenNothingHasAPlaceLeft:
    def test_the_answer_is_returned_rather_than_raised(
        self,
        make_offer_to_applicant: MakeOfferToApplicant,
        cycles: AdmissionCycleRepositoryPort,
        requirements: ProgramEntryRequirementRepositoryPort,
        policies: AlternativeProgramPolicyRepositoryPort,
    ) -> None:
        """No ``pytest.raises`` here on purpose: most applicants are told no, normally."""
        cycles.add(a_full_cycle(COMPUTER_SCIENCE))
        cycles.add(a_full_cycle(MATHEMATICS))
        cycles.add(a_full_cycle(STATISTICS))
        requirements.add(a_science_requirement(MATHEMATICS))
        requirements.add(a_science_requirement(STATISTICS))
        policies.add(a_policy((MATHEMATICS, STATISTICS)))

        decision = make_offer_to_applicant.execute(COMMAND)

        assert decision == NoOfferAvailable(
            applicant_id=APPLICANT_ID,
            applied_program_id=COMPUTER_SCIENCE,
            considered=(COMPUTER_SCIENCE, MATHEMATICS, STATISTICS),
        )

    @pytest.mark.usefixtures("overflow_chain")
    def test_the_application_is_closed_and_final(
        self,
        make_offer_to_applicant: MakeOfferToApplicant,
        applicants: ApplicantRepositoryPort,
        cycles: AdmissionCycleRepositoryPort,
    ) -> None:
        cycles.add(a_full_cycle(COMPUTER_SCIENCE))
        cycles.add(a_full_cycle(PHYSICS))
        cycles.add(a_full_cycle(MATHEMATICS))

        make_offer_to_applicant.execute(COMMAND)

        applicant = stored(applicants)
        assert applicant.status is ApplicationStatus.NO_OFFER_AVAILABLE
        assert applicant.is_final is True
        assert applicant.offered_program_id is None

    @pytest.mark.usefixtures("overflow_chain")
    def test_not_one_place_was_claimed_anywhere(
        self, make_offer_to_applicant: MakeOfferToApplicant, cycles: AdmissionCycleRepositoryPort
    ) -> None:
        cycles.add(a_cycle(COMPUTER_SCIENCE, quota=2, offers_made=2))
        cycles.add(a_cycle(PHYSICS, quota=3, offers_made=3))
        cycles.add(a_cycle(MATHEMATICS, quota=4, offers_made=4))

        make_offer_to_applicant.execute(COMMAND)

        assert offers_made_on(cycles, COMPUTER_SCIENCE) == 2
        assert offers_made_on(cycles, PHYSICS) == 3
        assert offers_made_on(cycles, MATHEMATICS) == 4

    def test_a_program_with_no_published_policy_has_no_fallback(
        self, make_offer_to_applicant: MakeOfferToApplicant, cycles: AdmissionCycleRepositoryPort
    ) -> None:
        """Not every program overflows anywhere, and demanding a chain would invent policy."""
        cycles.add(a_full_cycle(COMPUTER_SCIENCE))

        decision = make_offer_to_applicant.execute(COMMAND)

        assert decision == NoOfferAvailable(
            applicant_id=APPLICANT_ID,
            applied_program_id=COMPUTER_SCIENCE,
            considered=(COMPUTER_SCIENCE,),
        )

    def test_an_empty_published_chain_is_the_same_answer(
        self,
        make_offer_to_applicant: MakeOfferToApplicant,
        cycles: AdmissionCycleRepositoryPort,
        policies: AlternativeProgramPolicyRepositoryPort,
    ) -> None:
        cycles.add(a_full_cycle(COMPUTER_SCIENCE))
        policies.add(a_policy(()))

        decision = make_offer_to_applicant.execute(COMMAND)

        assert isinstance(decision, NoOfferAvailable)
        assert decision.considered == (COMPUTER_SCIENCE,)

    def test_a_program_admitting_nobody_is_full_from_the_moment_it_opens(
        self, make_offer_to_applicant: MakeOfferToApplicant, cycles: AdmissionCycleRepositoryPort
    ) -> None:
        """A quota of zero needs no second notion of "closed" anywhere in this flow."""
        cycles.add(a_cycle(COMPUTER_SCIENCE, quota=0))

        decision = make_offer_to_applicant.execute(COMMAND)

        assert isinstance(decision, NoOfferAvailable)

    @pytest.mark.usefixtures("overflow_chain")
    def test_every_program_examined_is_named_in_order(
        self, make_offer_to_applicant: MakeOfferToApplicant, cycles: AdmissionCycleRepositoryPort
    ) -> None:
        """So somebody can answer "was I even looked at for Physics?" without re-running it."""
        cycles.add(a_full_cycle(COMPUTER_SCIENCE))
        cycles.add(a_full_cycle(PHYSICS))
        cycles.add(a_full_cycle(MATHEMATICS))

        decision = make_offer_to_applicant.execute(COMMAND)

        assert isinstance(decision, NoOfferAvailable)
        assert decision.considered == (COMPUTER_SCIENCE, PHYSICS, MATHEMATICS)


class TestWhatTheFlowRefusesToDo:
    def test_an_unknown_applicant_is_an_error(
        self, make_offer_to_applicant: MakeOfferToApplicant, cycles: AdmissionCycleRepositoryPort
    ) -> None:
        cycles.add(a_cycle(COMPUTER_SCIENCE))

        with pytest.raises(ApplicantNotFoundError):
            make_offer_to_applicant.execute(MakeOfferToApplicantCommand("app-nobody"))

    @pytest.mark.usefixtures("screened_application")
    def test_an_applied_program_with_no_open_cycle_is_an_error(
        self, make_offer_to_applicant: MakeOfferToApplicant
    ) -> None:
        """Unlike an alternative's: without this cycle there is no question to answer."""
        with pytest.raises(AdmissionCycleNotFoundError):
            make_offer_to_applicant.execute(COMMAND)

    def test_an_unscreened_applicant_is_the_domains_refusal(
        self, make_offer_to_applicant: MakeOfferToApplicant, applicants: ApplicantRepositoryPort
    ) -> None:
        applicant = Applicant.apply(
            applicant_id=APPLICANT_ID,
            applied_program_id=COMPUTER_SCIENCE,
            session_id=SESSION_ID,
            bio_data=BIO,
            utme_result=UtmeResult(
                tuple(UtmeSubjectScore(subject, 70) for subject in QUALIFYING_SUBJECTS)
            ),
        )
        applicants.add(applicant)

        with pytest.raises(ApplicantNotScreenedError):
            make_offer_to_applicant.execute(COMMAND)

    def test_an_unscreened_applicant_costs_nobody_a_place(
        self,
        make_offer_to_applicant: MakeOfferToApplicant,
        applicants: ApplicantRepositoryPort,
        cycles: AdmissionCycleRepositoryPort,
    ) -> None:
        """The refusal has to come before a place is claimed: two transactions, no rollback."""
        applicant = Applicant.apply(
            applicant_id=APPLICANT_ID,
            applied_program_id=COMPUTER_SCIENCE,
            session_id=SESSION_ID,
            bio_data=BIO,
            utme_result=UtmeResult(
                tuple(UtmeSubjectScore(subject, 70) for subject in QUALIFYING_SUBJECTS)
            ),
        )
        applicants.add(applicant)
        cycles.add(a_cycle(COMPUTER_SCIENCE))

        with pytest.raises(ApplicantNotScreenedError):
            make_offer_to_applicant.execute(COMMAND)

        assert offers_made_on(cycles, COMPUTER_SCIENCE) == 0

    @pytest.mark.usefixtures("screened_application")
    def test_an_applicant_who_already_holds_an_offer_cannot_be_offered_again(
        self,
        make_offer_to_applicant: MakeOfferToApplicant,
        cycles: AdmissionCycleRepositoryPort,
    ) -> None:
        cycles.add(a_cycle(COMPUTER_SCIENCE, quota=5))
        make_offer_to_applicant.execute(COMMAND)

        with pytest.raises(OfferAlreadyMadeError):
            make_offer_to_applicant.execute(COMMAND)

        assert offers_made_on(cycles, COMPUTER_SCIENCE) == 1

    @pytest.mark.usefixtures("screened_application")
    def test_an_application_that_already_ended_cannot_be_offered_anything(
        self, make_offer_to_applicant: MakeOfferToApplicant, cycles: AdmissionCycleRepositoryPort
    ) -> None:
        cycles.add(a_full_cycle(COMPUTER_SCIENCE))
        make_offer_to_applicant.execute(COMMAND)

        with pytest.raises(ApplicationOutcomeFinalError):
            make_offer_to_applicant.execute(COMMAND)


@pytest.mark.usefixtures("screened_application")
class TestEverythingIsReadForTheApplicantsOwnSession:
    def test_a_cycle_opened_for_another_session_is_not_this_applicants(
        self, make_offer_to_applicant: MakeOfferToApplicant, cycles: AdmissionCycleRepositoryPort
    ) -> None:
        cycles.add(a_cycle(COMPUTER_SCIENCE, session_id=OTHER_SESSION_ID))

        with pytest.raises(AdmissionCycleNotFoundError):
            make_offer_to_applicant.execute(COMMAND)

    def test_a_chain_published_for_another_session_is_not_consulted(
        self,
        make_offer_to_applicant: MakeOfferToApplicant,
        cycles: AdmissionCycleRepositoryPort,
        requirements: ProgramEntryRequirementRepositoryPort,
        policies: AlternativeProgramPolicyRepositoryPort,
    ) -> None:
        """Where Computer Science overflowed last year is not where it overflows this year."""
        cycles.add(a_full_cycle(COMPUTER_SCIENCE))
        cycles.add(a_cycle(MATHEMATICS))
        requirements.add(a_science_requirement(MATHEMATICS))
        policies.add(a_policy((MATHEMATICS,), session_id=OTHER_SESSION_ID))

        decision = make_offer_to_applicant.execute(COMMAND)

        assert isinstance(decision, NoOfferAvailable)
        assert offers_made_on(cycles, MATHEMATICS) == 0

    def test_an_alternatives_requirement_is_read_for_this_session(
        self,
        make_offer_to_applicant: MakeOfferToApplicant,
        cycles: AdmissionCycleRepositoryPort,
        requirements: ProgramEntryRequirementRepositoryPort,
        policies: AlternativeProgramPolicyRepositoryPort,
    ) -> None:
        cycles.add(a_full_cycle(COMPUTER_SCIENCE))
        cycles.add(a_cycle(MATHEMATICS))
        requirements.add(a_science_requirement(MATHEMATICS, session_id=OTHER_SESSION_ID))
        policies.add(a_policy((MATHEMATICS,)))

        decision = make_offer_to_applicant.execute(COMMAND)

        assert isinstance(decision, NoOfferAvailable)
        assert offers_made_on(cycles, MATHEMATICS) == 0
