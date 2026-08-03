"""Link a matriculated party's ledger to the matric number they were issued.

The second half of CLAUDE.md's party-id: "applicant_id before matriculation, linked to matric
number after". One continuous ledger from the acceptance fee onward — it does not close and
reopen when somebody becomes a student, it gains a second name.

**Nothing drives this yet, and that is stated rather than hidden.** No event in the system
carries a matric number: ``StudentMatriculated`` deliberately has none in its payload
(CLAUDE.md section 3), and Student Profile — which issues them — publishes nothing at all
today. So there is no inbound handler here, because a handler subscribing to an event nobody
publishes is wiring that cannot be wrong and cannot be right. What exists is the use case an
administrative interface calls, and what a future ``StudentRegistered``-style event would call
when somebody decides to publish one.
"""

from dataclasses import dataclass

from billing.application.errors import AccountNotFoundError
from billing.ports.account_repository import AccountRepositoryPort


@dataclass(frozen=True)
class LinkStudentAccountCommand:
    """The party as Billing knows them, and the matric number they now hold."""

    party_id: str
    student_id: str


@dataclass(frozen=True)
class StudentAccountLinked:
    """The two ids that now reach one ledger, and whether this call is what joined them."""

    party_id: str
    student_id: str
    was_already_linked: bool


class LinkStudentAccount:
    """Give an applicant's ledger the matric number its owner was issued."""

    def __init__(self, accounts: AccountRepositoryPort) -> None:
        self._accounts = accounts

    def execute(self, command: LinkStudentAccountCommand) -> StudentAccountLinked:
        """Link the account, or report that it was already linked to this id.

        Raises:
            AccountNotFoundError: no ledger exists for that party.
            PartyAlreadyLinkedError: the ledger already answers to a *different* matric
                number. One ledger for two people would leave nobody able to say whose money
                was whose.
        """
        account = self._accounts.get(command.party_id)
        if account is None:
            raise AccountNotFoundError(
                f"no billing account is stored for party {command.party_id!r}, so it cannot "
                f"be linked to student {command.student_id!r}"
            )

        linked_now = account.link_student_id(command.student_id)
        if linked_now:
            self._accounts.save(account)

        return StudentAccountLinked(
            party_id=account.party_id,
            student_id=command.student_id,
            was_already_linked=not linked_now,
        )
