"""Dict-backed ``AccountRepositoryPort``, keyed by party-id and resolving either of a party's ids.

The alias index is the one thing this adapter does that the other in-memory repositories in
the system do not, and it is where the party-id abstraction is actually paid for. An account
is stored under the id it was opened with — the applicant id — and answers to the matric
number it is later linked to as well, so a caller holding one id never has to know which era
it belongs to.

The index is rebuilt from the account on every ``add`` and ``save`` rather than maintained by
hand, because the aggregate is the authority on which ids it answers to and a second copy of
that knowledge would eventually disagree with it. Under Postgres the same thing is a unique
index on a nullable column; here it is a dict, and it is the reason ``link_student_id``'s
effect has to be saved to be visible.
"""

from billing.adapters.outbound._store import InMemoryStore
from billing.domain.account import Account
from billing.ports.account_repository import AccountRepositoryPort


class InMemoryAccountRepository(AccountRepositoryPort):
    """Holds accounts in memory for the duration of the process."""

    def __init__(self) -> None:
        self._store = InMemoryStore[Account]("account", lambda account: account.party_id)
        self._aliases: dict[str, str] = {}

    async def add(self, account: Account) -> None:
        self._store.add(account)
        self._index(account)

    async def save(self, account: Account) -> None:
        self._store.save(account)
        self._index(account)

    async def get(self, party_id: str) -> Account | None:
        """Resolve the id directly, then through the alias index."""
        direct = self._store.get(party_id)
        if direct is not None:
            return direct
        aliased = self._aliases.get(party_id)
        return self._store.get(aliased) if aliased is not None else None

    async def all_active(self) -> tuple[Account, ...]:
        """Every account held, in the order opened. Nothing closes one in the MVP."""
        return self._store.all()

    def _index(self, account: Account) -> None:
        """Point every id this account answers to at its storage key."""
        for party_id in account.party_ids:
            self._aliases[party_id] = account.party_id
