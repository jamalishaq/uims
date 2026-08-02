"""Whether four subjects qualify somebody for a program, using requirements LASU writes.

The combinations here are the real shape of a Nigerian entry requirement: some subjects
demanded of everybody, and a slot the applicant chooses from a list. Testing with invented
requirements — three required subjects and nothing else — would never exercise the case
the model exists for, which is Law wanting two separate choices at once.

Two failure modes are worth stating out loud, because each turns real people away or lets
them through:

* An extra subject the program never asked about must not disqualify anyone. Every UTME
  result carries four subjects whether the program wanted four or one.
* A subject must satisfy one demand, not two. The requirement refuses to be written with
  overlapping demands at all, which is what keeps the rule a straight read.

Zero infrastructure: a requirement, a result, and the rule between them.
"""

import pytest

from admissions.domain import (
    UTME_SUBJECT_COUNT,
    InvalidSubjectGroupError,
    MissingIdentifierError,
    OverlappingRequirementError,
    ProgramEntryRequirement,
    SubjectCombinationRule,
    SubjectGroup,
    UnsatisfiableRequirementError,
    UtmeResult,
    UtmeSubjectScore,
)

SESSION_ID = "sess-2026"

COMPUTER_SCIENCE = ProgramEntryRequirement.for_program(
    "prg-csc",
    SESSION_ID,
    required_subjects=("USE OF ENGLISH", "MATHEMATICS", "PHYSICS"),
    one_of_groups=(
        SubjectGroup(
            frozenset({"CHEMISTRY", "BIOLOGY", "GEOGRAPHY", "ECONOMICS", "AGRICULTURAL SCIENCE"})
        ),
    ),
)

MEDICINE = ProgramEntryRequirement.for_program(
    "prg-mbbs",
    SESSION_ID,
    required_subjects=("USE OF ENGLISH", "BIOLOGY", "CHEMISTRY", "PHYSICS"),
)

ACCOUNTING = ProgramEntryRequirement.for_program(
    "prg-acc",
    SESSION_ID,
    required_subjects=("USE OF ENGLISH", "MATHEMATICS", "ECONOMICS"),
    one_of_groups=(
        SubjectGroup(frozenset({"ACCOUNTING", "COMMERCE", "BUSINESS STUDIES", "GOVERNMENT"})),
    ),
)

LAW = ProgramEntryRequirement.for_program(
    "prg-law",
    SESSION_ID,
    required_subjects=("USE OF ENGLISH", "LITERATURE IN ENGLISH"),
    one_of_groups=(
        SubjectGroup(frozenset({"GOVERNMENT", "HISTORY"})),
        SubjectGroup(frozenset({"CRS", "IRS", "ECONOMICS"})),
    ),
)

RULE = SubjectCombinationRule()


def a_result(*subjects: str) -> UtmeResult:
    """A four-subject result in the given subjects, scoring 70 in each.

    The scores are beside the point here: this file is about combinations, and a rule that
    read scores would be a rule that had quietly grown a cut-off mark.
    """
    return UtmeResult(tuple(UtmeSubjectScore(subject, 70) for subject in subjects))


class TestSubjectGroup:
    def test_a_group_is_satisfied_by_any_one_of_its_options(self) -> None:
        group = SubjectGroup(frozenset({"CHEMISTRY", "BIOLOGY"}))

        assert group.satisfied_by(frozenset({"BIOLOGY", "MATHEMATICS"})) is True

    def test_holding_two_options_is_no_better_and_no_worse_than_holding_one(self) -> None:
        group = SubjectGroup(frozenset({"CHEMISTRY", "BIOLOGY"}))

        assert group.satisfied_by(frozenset({"CHEMISTRY", "BIOLOGY"})) is True

    def test_a_group_none_of_whose_options_were_sat_is_unsatisfied(self) -> None:
        group = SubjectGroup(frozenset({"CHEMISTRY", "BIOLOGY"}))

        assert group.satisfied_by(frozenset({"MATHEMATICS", "PHYSICS"})) is False

    def test_options_are_held_upper_cased_and_stripped(self) -> None:
        group = SubjectGroup(frozenset({" chemistry ", "Biology"}))

        assert group.options == frozenset({"CHEMISTRY", "BIOLOGY"})

    def test_a_group_reads_as_the_choice_it_offers(self) -> None:
        group = SubjectGroup(frozenset({"CHEMISTRY", "BIOLOGY", "GEOGRAPHY"}))

        assert str(group) == "one of {BIOLOGY, CHEMISTRY, GEOGRAPHY}"

    def test_a_group_offering_nothing_is_rejected(self) -> None:
        with pytest.raises(InvalidSubjectGroupError):
            SubjectGroup(frozenset())

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_a_blank_option_is_rejected(self, blank: str) -> None:
        with pytest.raises(MissingIdentifierError):
            SubjectGroup(frozenset({blank}))


class TestWritingARequirement:
    def test_a_requirement_holds_the_demands_it_was_written_with(self) -> None:
        assert COMPUTER_SCIENCE.program_id == "prg-csc"
        assert COMPUTER_SCIENCE.session_id == SESSION_ID
        assert COMPUTER_SCIENCE.required_subjects == frozenset(
            {"USE OF ENGLISH", "MATHEMATICS", "PHYSICS"}
        )
        assert len(COMPUTER_SCIENCE.one_of_groups) == 1
        assert COMPUTER_SCIENCE.demand_count == UTME_SUBJECT_COUNT

    def test_subjects_are_normalised_the_way_a_sat_subject_is(self) -> None:
        """The two normalisations must agree, or no applicant would ever match."""
        requirement = ProgramEntryRequirement.for_program(
            "prg-csc", SESSION_ID, required_subjects=(" use of english ", "Mathematics")
        )

        assert requirement.required_subjects == frozenset({"USE OF ENGLISH", "MATHEMATICS"})

    def test_a_requirement_demanding_nothing_is_legal(self) -> None:
        """A program admitting on aggregate alone is real; inventing a subject is not."""
        requirement = ProgramEntryRequirement.for_program("prg-open", SESSION_ID)

        assert requirement.demand_count == 0
        assert RULE.qualifies(requirement, a_result("A", "B", "C", "D")) is True

    def test_a_requirement_nobody_could_ever_satisfy_is_rejected(self) -> None:
        """Five demands against four subjects is a policy typo, not a strict programme."""
        with pytest.raises(UnsatisfiableRequirementError):
            ProgramEntryRequirement.for_program(
                "prg-csc",
                SESSION_ID,
                required_subjects=("USE OF ENGLISH", "MATHEMATICS", "PHYSICS", "CHEMISTRY"),
                one_of_groups=(SubjectGroup(frozenset({"BIOLOGY", "GEOGRAPHY"})),),
            )

    def test_a_group_overlapping_a_required_subject_is_rejected(self) -> None:
        """One subject may answer one demand; counting it twice would admit the unqualified."""
        with pytest.raises(OverlappingRequirementError):
            ProgramEntryRequirement.for_program(
                "prg-csc",
                SESSION_ID,
                required_subjects=("MATHEMATICS",),
                one_of_groups=(SubjectGroup(frozenset({"MATHEMATICS", "FURTHER MATHEMATICS"})),),
            )

    def test_two_groups_sharing_an_option_are_rejected(self) -> None:
        with pytest.raises(OverlappingRequirementError):
            ProgramEntryRequirement.for_program(
                "prg-law",
                SESSION_ID,
                one_of_groups=(
                    SubjectGroup(frozenset({"GOVERNMENT", "HISTORY"})),
                    SubjectGroup(frozenset({"GOVERNMENT", "CRS"})),
                ),
            )

    @pytest.mark.parametrize("field", ["program_id", "session_id"])
    @pytest.mark.parametrize("blank", ["", "   "])
    def test_a_blank_identifier_is_rejected(self, field: str, blank: str) -> None:
        ids = {"program_id": "prg-csc", "session_id": SESSION_ID, field: blank}

        with pytest.raises(MissingIdentifierError):
            ProgramEntryRequirement.for_program(**ids)  # type: ignore[arg-type]

    def test_one_of_groups_must_be_subject_groups(self) -> None:
        with pytest.raises(InvalidSubjectGroupError):
            ProgramEntryRequirement.for_program(
                "prg-csc",
                SESSION_ID,
                one_of_groups=({"BIOLOGY", "CHEMISTRY"},),  # type: ignore[arg-type]
            )


class TestQualifyingForAProgram:
    def test_a_science_combination_with_the_chosen_fourth_subject_qualifies(self) -> None:
        result = a_result("USE OF ENGLISH", "MATHEMATICS", "PHYSICS", "CHEMISTRY")

        assert RULE.qualifies(COMPUTER_SCIENCE, result) is True
        assert RULE.unmet(COMPUTER_SCIENCE, result) == ()

    def test_any_option_in_the_group_serves_as_well_as_any_other(self) -> None:
        for chosen in ("CHEMISTRY", "BIOLOGY", "GEOGRAPHY", "ECONOMICS", "AGRICULTURAL SCIENCE"):
            result = a_result("USE OF ENGLISH", "MATHEMATICS", "PHYSICS", chosen)

            assert RULE.qualifies(COMPUTER_SCIENCE, result) is True

    def test_a_missing_required_subject_is_named(self) -> None:
        result = a_result("USE OF ENGLISH", "MATHEMATICS", "BIOLOGY", "CHEMISTRY")

        assert RULE.qualifies(COMPUTER_SCIENCE, result) is False
        assert RULE.unmet(COMPUTER_SCIENCE, result) == ("PHYSICS",)

    def test_a_choice_met_by_none_of_its_options_is_rendered_whole(self) -> None:
        """Naming one option would read as advice the program never gave."""
        result = a_result("USE OF ENGLISH", "MATHEMATICS", "PHYSICS", "FURTHER MATHEMATICS")

        assert RULE.unmet(COMPUTER_SCIENCE, result) == (
            "one of {AGRICULTURAL SCIENCE, BIOLOGY, CHEMISTRY, ECONOMICS, GEOGRAPHY}",
        )

    def test_every_unmet_demand_is_reported_not_just_the_first(self) -> None:
        result = a_result("USE OF ENGLISH", "GOVERNMENT", "HISTORY", "CRS")

        assert RULE.unmet(COMPUTER_SCIENCE, result) == (
            "MATHEMATICS",
            "PHYSICS",
            "one of {AGRICULTURAL SCIENCE, BIOLOGY, CHEMISTRY, ECONOMICS, GEOGRAPHY}",
        )

    def test_a_requirement_of_four_required_subjects_needs_all_four(self) -> None:
        exact = a_result("USE OF ENGLISH", "BIOLOGY", "CHEMISTRY", "PHYSICS")
        short = a_result("USE OF ENGLISH", "BIOLOGY", "CHEMISTRY", "MATHEMATICS")

        assert RULE.qualifies(MEDICINE, exact) is True
        assert RULE.unmet(MEDICINE, short) == ("PHYSICS",)

    def test_a_commercial_combination_qualifies_on_its_chosen_subject(self) -> None:
        result = a_result("USE OF ENGLISH", "MATHEMATICS", "ECONOMICS", "COMMERCE")

        assert RULE.qualifies(ACCOUNTING, result) is True

    def test_two_choices_must_both_be_answered(self) -> None:
        """Law wants an arts subject *and* a social-science one; one of each, not one of two."""
        both = a_result("USE OF ENGLISH", "LITERATURE IN ENGLISH", "GOVERNMENT", "CRS")
        only_one = a_result("USE OF ENGLISH", "LITERATURE IN ENGLISH", "GOVERNMENT", "PHYSICS")
        neither = a_result("USE OF ENGLISH", "LITERATURE IN ENGLISH", "PHYSICS", "MATHEMATICS")

        assert RULE.qualifies(LAW, both) is True
        assert RULE.unmet(LAW, only_one) == ("one of {CRS, ECONOMICS, IRS}",)
        assert RULE.unmet(LAW, neither) == (
            "one of {GOVERNMENT, HISTORY}",
            "one of {CRS, ECONOMICS, IRS}",
        )

    def test_a_subject_the_program_never_asked_about_disqualifies_nobody(self) -> None:
        requirement = ProgramEntryRequirement.for_program(
            "prg-open", SESSION_ID, required_subjects=("USE OF ENGLISH",)
        )
        result = a_result("USE OF ENGLISH", "MUSIC", "FRENCH", "VISUAL ARTS")

        assert RULE.qualifies(requirement, result) is True

    def test_case_and_spacing_never_decide_an_admission(self) -> None:
        """A requirement written in title case must match a result held in upper case."""
        requirement = ProgramEntryRequirement.for_program(
            "prg-csc",
            SESSION_ID,
            required_subjects=(" Use of English ",),
            one_of_groups=(SubjectGroup(frozenset({" chemistry ", "biology"})),),
        )
        result = a_result("USE OF ENGLISH", "CHEMISTRY", "MATHEMATICS", "PHYSICS")

        assert RULE.qualifies(requirement, result) is True

    @pytest.mark.parametrize(
        "requirement",
        [
            pytest.param(COMPUTER_SCIENCE, id="computer_science"),
            pytest.param(MEDICINE, id="medicine"),
            pytest.param(ACCOUNTING, id="accounting"),
            pytest.param(LAW, id="law"),
        ],
    )
    @pytest.mark.parametrize(
        "result",
        [
            pytest.param(
                a_result("USE OF ENGLISH", "MATHEMATICS", "PHYSICS", "CHEMISTRY"), id="science"
            ),
            pytest.param(
                a_result("USE OF ENGLISH", "MATHEMATICS", "ECONOMICS", "COMMERCE"), id="commercial"
            ),
            pytest.param(
                a_result("USE OF ENGLISH", "LITERATURE IN ENGLISH", "GOVERNMENT", "CRS"), id="arts"
            ),
        ],
    )
    def test_the_verdict_and_the_explanation_never_disagree(
        self, requirement: ProgramEntryRequirement, result: UtmeResult
    ) -> None:
        """A rule that decided in one place and explained in another would eventually drift."""
        assert RULE.qualifies(requirement, result) is (RULE.unmet(requirement, result) == ())
