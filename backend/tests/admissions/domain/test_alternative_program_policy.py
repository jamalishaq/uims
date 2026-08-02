"""Order is the content: a fallback chain that lost its order would place people elsewhere.

``MakeOfferToApplicant`` takes the *first* qualifying alternative with room, so the
sequence in this object decides who ends up on Mathematics and who ends up on Statistics.
The test that matters most here is the dull-looking one asserting the tuple comes back in
the order it went in — if that ever fails, offers have quietly started depending on hash
order and nobody would see it in an offer letter.

The two rejections are policy typos caught at the moment the policy is written. Both are
things that could never do anything except waste a lookup, which is exactly why nobody
would notice them at run time.

Zero infrastructure: one aggregate, built directly.
"""

import pytest

from admissions.domain import (
    AlternativeProgramPolicy,
    DuplicateAlternativeError,
    MissingIdentifierError,
    SelfReferentialAlternativeError,
)

PROGRAM_ID = "prg-csc"
SESSION_ID = "sess-2026"
MATHEMATICS = "prg-mth"
STATISTICS = "prg-sta"
PHYSICS = "prg-phy"


def a_policy(
    alternatives: tuple[str, ...] = (MATHEMATICS, STATISTICS),
    **overrides: object,
) -> AlternativeProgramPolicy:
    fields: dict[str, object] = {
        "program_id": PROGRAM_ID,
        "session_id": SESSION_ID,
        "alternatives": alternatives,
    }
    fields.update(overrides)
    return AlternativeProgramPolicy(**fields)  # type: ignore[arg-type]


class TestPublishingAChain:
    def test_the_alternatives_come_back_in_the_order_they_were_written(self) -> None:
        """Preference order, not membership: first qualifying alternative with room wins."""
        policy = a_policy((PHYSICS, MATHEMATICS, STATISTICS))

        assert policy.alternatives == (PHYSICS, MATHEMATICS, STATISTICS)

    def test_a_program_may_have_no_alternatives_at_all(self) -> None:
        """Some programs overflow nowhere, and demanding a token fallback would invent policy."""
        policy = a_policy(())

        assert policy.alternatives == ()

    def test_the_chain_is_a_tuple_a_caller_cannot_reorder(self) -> None:
        policy = a_policy()

        assert isinstance(policy.alternatives, tuple)

    def test_it_remembers_which_program_and_session_it_speaks_for(self) -> None:
        policy = a_policy()

        assert policy.program_id == PROGRAM_ID
        assert policy.session_id == SESSION_ID

    def test_for_program_publishes_the_same_thing_the_constructor_does(self) -> None:
        published = AlternativeProgramPolicy.for_program(PROGRAM_ID, SESSION_ID, (MATHEMATICS,))

        assert published.program_id == PROGRAM_ID
        assert published.alternatives == (MATHEMATICS,)


class TestPolicyTyposCaughtWhenWritten:
    def test_a_program_may_not_be_its_own_alternative(self) -> None:
        """The chain is only ever read because that cycle was full; a retry finds it full."""
        with pytest.raises(SelfReferentialAlternativeError):
            a_policy((MATHEMATICS, PROGRAM_ID))

    def test_a_program_may_not_appear_twice(self) -> None:
        """First match wins, so a repeat is unreachable — it is a finger slipping, not a chain."""
        with pytest.raises(DuplicateAlternativeError):
            a_policy((MATHEMATICS, STATISTICS, MATHEMATICS))

    def test_the_duplicate_is_named_so_the_typo_can_be_found(self) -> None:
        with pytest.raises(DuplicateAlternativeError, match=MATHEMATICS):
            a_policy((MATHEMATICS, STATISTICS, MATHEMATICS))

    @pytest.mark.parametrize(
        "field",
        [
            pytest.param("program_id", id="program_id"),
            pytest.param("session_id", id="session_id"),
        ],
    )
    def test_a_blank_identifier_is_refused(self, field: str) -> None:
        with pytest.raises(MissingIdentifierError):
            a_policy(**{field: "   "})

    def test_a_blank_alternative_is_refused(self) -> None:
        with pytest.raises(MissingIdentifierError):
            a_policy((MATHEMATICS, ""))
