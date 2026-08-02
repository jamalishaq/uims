"""Where an applicant goes when the program they wanted is full.

Admissions-owned policy data, scoped to a session exactly as ``ProgramEntryRequirement``
is (CLAUDE.md section 3). A Nigerian university that cannot seat every qualified
applicant on their first choice does not simply turn them away: Computer Science
overflows into Mathematics, into Statistics, into Physics, in an order the faculty
decided. That order is policy, written down before the cycle opens, and this is where it
is written.

Order is the whole content of this object, which is why ``alternatives`` is a tuple and
not a set. First qualifying program with a place left gets the applicant
(``MakeOfferToApplicant``), so re-ordering the list changes who ends up where — a set
would lose the decision and let the answer depend on hash order.

Two construction guards, both catching a policy typo at the moment it is written rather
than at the moment a cohort is placed:

* A program may not be its own alternative. The alternatives list is only ever consulted
  *because* that program's cycle came back ``QuotaExhausted``, and a full cycle does not
  become less full on a second ask — the entry could never do anything but waste a
  lookup.
* A program may not appear twice. "First qualifying cycle with room" makes the second
  occurrence unreachable, so a duplicate is never a longer fallback chain; it is
  somebody's finger slipping.

What is *not* here is any judgement about whether an applicant may take an alternative.
Whether their subjects qualify them for it is ``SubjectCombinationRule``'s call and
whether it has a place left is ``AdmissionCycle``'s — the same two judgements the applied
program went through, asked again of a different program. This object only says which
programs to ask, and in what order.
"""

from collections.abc import Iterable

from admissions.domain.errors import DuplicateAlternativeError, SelfReferentialAlternativeError
from admissions.domain.values import require_identifier


class AlternativeProgramPolicy:
    """The programs one program overflows into for one session, in preference order."""

    def __init__(
        self,
        program_id: str,
        session_id: str,
        alternatives: Iterable[str] = (),
    ) -> None:
        self._program_id = require_identifier(program_id, "program_id")
        self._session_id = require_identifier(session_id, "session_id")
        self._alternatives = tuple(
            require_identifier(alternative, "alternative") for alternative in alternatives
        )
        self._reject_self_reference()
        self._reject_duplicates()

    @classmethod
    def for_program(
        cls,
        program_id: str,
        session_id: str,
        alternatives: Iterable[str] = (),
    ) -> "AlternativeProgramPolicy":
        """Publish a program's fallback chain for a session.

        An empty chain is legal and means the program has no fallback: an applicant it
        cannot seat is told no offer is available. Some programs genuinely have nowhere
        to overflow to, and demanding a token alternative would be inventing policy.
        """
        return cls(program_id, session_id, alternatives)

    @property
    def program_id(self) -> str:
        """The program this is the fallback chain *for*, not one of the fallbacks."""
        return self._program_id

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def alternatives(self) -> tuple[str, ...]:
        """The programs to try, best first. A tuple: callers cannot re-order the policy."""
        return self._alternatives

    def _reject_self_reference(self) -> None:
        if self._program_id in self._alternatives:
            raise SelfReferentialAlternativeError(
                f"policy for program {self._program_id} lists itself as an alternative; "
                "the cycle it would retry is the one already found full"
            )

    def _reject_duplicates(self) -> None:
        seen: set[str] = set()
        repeated: set[str] = set()
        for alternative in self._alternatives:
            if alternative in seen:
                repeated.add(alternative)
            seen.add(alternative)
        if repeated:
            raise DuplicateAlternativeError(
                f"policy for program {self._program_id} names "
                f"{', '.join(sorted(repeated))} more than once"
            )

    def __repr__(self) -> str:
        return (
            f"AlternativeProgramPolicy(program_id={self._program_id!r}, "
            f"session_id={self._session_id!r}, alternatives={list(self._alternatives)})"
        )
