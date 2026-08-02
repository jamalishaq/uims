"""The contract the Admissions repository adapters must keep.

This is the one file in the context's suite that names the adapters directly, because it
is the adapters that are under test. The Postgres adapters of Phase 6 have to pass this
same file — where the two would disagree is exactly the drift this catches.

The requirement repository gets more attention than its size suggests, because it is the
one with a composite key. ``(program_id, session_id)`` is flattened into a single stored
key here and will become two columns under Postgres, and the thing that must survive that
translation is that a program's requirement for one session never stands in for another's.
"""

from datetime import date

import pytest

from admissions.adapters.outbound import (
    InMemoryApplicantRepository,
    InMemoryProgramEntryRequirementRepository,
)
from admissions.domain import (
    Applicant,
    BioData,
    ProgramEntryRequirement,
    SubjectGroup,
    UtmeResult,
    UtmeSubjectScore,
)
from admissions.ports import AggregateNotFoundError, DuplicateAggregateError

PROGRAM_ID = "prg-csc"
SESSION_ID = "sess-2026"
OTHER_SESSION_ID = "sess-2027"

BIO = BioData("Adaeze Okonkwo", date_of_birth=date(2006, 4, 1))
UTME = UtmeResult(
    (
        UtmeSubjectScore("USE OF ENGLISH", 78),
        UtmeSubjectScore("MATHEMATICS", 65),
        UtmeSubjectScore("PHYSICS", 70),
        UtmeSubjectScore("CHEMISTRY", 62),
    )
)


def an_applicant(applicant_id: str = "app-0001", session_id: str = SESSION_ID) -> Applicant:
    return Applicant.apply(applicant_id, PROGRAM_ID, session_id, BIO, UTME)


def a_requirement(
    program_id: str = PROGRAM_ID, session_id: str = SESSION_ID
) -> ProgramEntryRequirement:
    return ProgramEntryRequirement.for_program(
        program_id,
        session_id,
        required_subjects=("USE OF ENGLISH", "MATHEMATICS"),
        one_of_groups=(SubjectGroup(frozenset({"PHYSICS", "CHEMISTRY"})),),
    )


class TestApplicantStorageContract:
    def test_an_added_applicant_comes_back(self) -> None:
        repository = InMemoryApplicantRepository()
        applicant = an_applicant()

        repository.add(applicant)

        assert repository.get("app-0001") is applicant

    def test_an_unknown_id_returns_none(self) -> None:
        """Absence is an answer, not a failure."""
        assert InMemoryApplicantRepository().get("app-nobody") is None

    def test_adding_a_second_applicant_under_the_same_id_is_refused(self) -> None:
        repository = InMemoryApplicantRepository()
        first = an_applicant()
        repository.add(first)

        with pytest.raises(DuplicateAggregateError):
            repository.add(an_applicant())

        assert repository.get("app-0001") is first

    def test_save_replaces_a_stored_applicant(self) -> None:
        repository = InMemoryApplicantRepository()
        repository.add(an_applicant())
        replacement = an_applicant()

        repository.save(replacement)

        assert repository.get("app-0001") is replacement

    def test_save_on_an_id_that_was_never_added_is_refused(self) -> None:
        repository = InMemoryApplicantRepository()

        with pytest.raises(AggregateNotFoundError):
            repository.save(an_applicant())

        assert repository.get("app-0001") is None

    def test_a_screened_applicant_keeps_the_status_it_was_saved_with(self) -> None:
        repository = InMemoryApplicantRepository()
        applicant = an_applicant()
        repository.add(applicant)
        applicant.screen()

        repository.save(applicant)

        stored = repository.get("app-0001")
        assert stored is not None
        assert stored.status is applicant.status


class TestListingApplicantsForASession:
    def test_applications_are_filtered_by_session(self) -> None:
        repository = InMemoryApplicantRepository()
        this_year = an_applicant("app-0001")
        repository.add(this_year)
        repository.add(an_applicant("app-0002", OTHER_SESSION_ID))

        assert repository.list_for_session(SESSION_ID) == (this_year,)

    def test_applications_are_listed_in_insertion_order(self) -> None:
        repository = InMemoryApplicantRepository()
        later, earlier = an_applicant("app-0009"), an_applicant("app-0001")
        repository.add(later)
        repository.add(earlier)

        assert repository.list_for_session(SESSION_ID) == (later, earlier)

    def test_a_session_nobody_applied_in_lists_nothing(self) -> None:
        repository = InMemoryApplicantRepository()
        repository.add(an_applicant())

        assert repository.list_for_session("sess-1999") == ()


class TestEntryRequirementStorageContract:
    def test_a_published_requirement_comes_back(self) -> None:
        repository = InMemoryProgramEntryRequirementRepository()
        requirement = a_requirement()

        repository.add(requirement)

        assert repository.get(PROGRAM_ID, SESSION_ID) is requirement

    def test_an_unpublished_requirement_returns_none(self) -> None:
        assert InMemoryProgramEntryRequirementRepository().get(PROGRAM_ID, SESSION_ID) is None

    def test_publishing_twice_for_the_same_program_and_session_is_refused(self) -> None:
        repository = InMemoryProgramEntryRequirementRepository()
        first = a_requirement()
        repository.add(first)

        with pytest.raises(DuplicateAggregateError):
            repository.add(a_requirement())

        assert repository.get(PROGRAM_ID, SESSION_ID) is first

    def test_save_on_a_pair_that_was_never_published_is_refused(self) -> None:
        repository = InMemoryProgramEntryRequirementRepository()

        with pytest.raises(AggregateNotFoundError):
            repository.save(a_requirement())

        assert repository.get(PROGRAM_ID, SESSION_ID) is None


class TestRequirementsAreScopedToASession:
    def test_one_program_can_hold_a_different_requirement_each_session(self) -> None:
        """Publishing this year's rule must not overwrite the one last year was screened on."""
        repository = InMemoryProgramEntryRequirementRepository()
        this_year = a_requirement(session_id=SESSION_ID)
        next_year = a_requirement(session_id=OTHER_SESSION_ID)

        repository.add(this_year)
        repository.add(next_year)

        assert repository.get(PROGRAM_ID, SESSION_ID) is this_year
        assert repository.get(PROGRAM_ID, OTHER_SESSION_ID) is next_year

    def test_two_programs_in_one_session_are_kept_apart(self) -> None:
        repository = InMemoryProgramEntryRequirementRepository()
        computing = a_requirement("prg-csc")
        physics = a_requirement("prg-phy")

        repository.add(computing)
        repository.add(physics)

        assert repository.get("prg-csc", SESSION_ID) is computing
        assert repository.get("prg-phy", SESSION_ID) is physics

    def test_a_pair_is_not_confused_with_its_halves_joined_differently(self) -> None:
        """``("prg-a", "b-sess")`` and ``("prg-a-b", "sess")`` are different requirements."""
        repository = InMemoryProgramEntryRequirementRepository()
        repository.add(a_requirement("prg-a", "b-sess"))

        assert repository.get("prg-a-b", "sess") is None
        assert repository.get("prg-a", "b-sess") is not None
