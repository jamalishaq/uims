"""Outbound port for storing and retrieving accounts."""

from abc import ABC, abstractmethod

from billing.domain.account import Account


class AccountRepositoryPort(ABC):
    """Persistence for the ``Account`` aggregate, keyed by party-id.

    Keyed by the party and not by a surrogate id of its own, for the reason Academic Records
    keys a record by its student: there is exactly one account per party and it is only ever
    reached by asking about a person.

    :meth:`get` resolves **either** of an account's ids. A party is their applicant id before
    matriculation and their matric number afterwards (CLAUDE.md's glossary), and the whole
    point of one continuous ledger is that a caller holding one id does not have to know which
    era it belongs to. An adapter implementing this against a table needs a second index; that
    is the cost of the party-id abstraction and it is paid here rather than by every caller.

    There is no ``remove``. A ledger is the university's record of money it asked for and
    money it received, and it is what a dispute years later is settled against. Refunds are a
    deferred admin use case (CLAUDE.md section 3) and would be entries, never deletions.
    """

    @abstractmethod
    async def add(self, account: Account) -> None:
        """Store an account for a party who did not have one.

        Raises:
            DuplicateAggregateError: an account is already held for that party.
        """

    @abstractmethod
    async def save(self, account: Account) -> None:
        """Persist changes to an account that is already stored.

        Raises:
            AggregateNotFoundError: no account was ever added for that party.
        """

    @abstractmethod
    async def get(self, party_id: str) -> Account | None:
        """Return the party's account, or ``None`` if they have never been charged.

        ``None`` is an answer and not a failure: it is the answer for every applicant who has
        not yet accepted an offer. Resolves an applicant id or a linked matric number alike.
        """

    @abstractmethod
    async def all_active(self) -> tuple[Account, ...]:
        """Every account a session's fees should be applied to, in the order opened.

        "Active" is the word CLAUDE.md section 3 uses — "batch-apply ``FeeSchedule`` to all
        active student accounts" — and today it means every account held: nothing in the MVP
        closes one, because when an account stops being billable (graduation, withdrawal) is
        an institutional fact nobody has stated (CLAUDE.md section 6). The name is where that
        rule will land when it arrives, so the batch does not have to change when it does.
        """
