"""What every Postgres repository in this context does the same way.

Five aggregates need the same four things: insert a parent row and its children, update them,
read them back, and list them in the order they were added. Written once here for the reason
``_store.py`` gives for the in-memory equivalent — five copies would be five chances for
``save`` to mean something subtly different in one of them.

**One transaction per operation, taken from the pool.** Not a long-lived session shared by
the repositories, and the reason is in the design rather than in convenience: CLAUDE.md
section 4 forbids a transaction spanning two aggregates, and every multi-aggregate flow in
this system — ``MakeOfferToApplicant``, ``RegisterForCourse``, ``ConfirmPayment`` — is
sequential orchestration whose ordering is chosen so that a crash in the middle leaves the
recoverable state. A session spanning a use case would quietly turn those two writes into one
and throw that reasoning away. It is also what lets concurrent tasks work: an ``AsyncSession``
is not safe to share, and ``get_or_start`` is asked to survive two hundred callers at once.

**An identity map, and why it is not a cache.** ``get`` reads the row every time — a write
that never landed comes back as ``None`` and the caller finds out. What the map adds is that
*the object handed back for an id this repository already holds is the same object*, which is
what the in-memory store gave for free by holding live references, and what
``assert students.get("stu-0001") is student`` in the existing suite asks for. Reconstitution
still runs on every read, so a mapping that has gone wrong raises here rather than hiding
behind a cached instance; ``tests/persistence/test_round_trip.py`` reads through a second
repository, with an empty map, to prove the row is what it claims to be.

**Keys are tuples throughout**, even where there is one column. Half the aggregates in this
system are keyed by a pair — an admission cycle is ``(program_id, session_id)``, an offering
is ``(course_id, term)`` — and a base that special-cased the single-column case would make
those repositories the exception rather than the rule.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import Row, Table, and_, delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from billing.adapters.outbound.postgres._errors import translating
from billing.ports.errors import AggregateNotFoundError
from persistence import resilient

type Key = tuple[Any, ...]


class PostgresRepository[T](ABC):
    """Insert, update and read one aggregate, with its children and its identity."""

    def __init__(
        self, engine: AsyncEngine, *, label: str, table: Table, key: Sequence[str]
    ) -> None:
        self._engine = engine
        self._label = label
        self._table = table
        self._key_columns = tuple(key)
        self._identities: dict[Key, T] = {}

    # ---- what each aggregate supplies ----

    @abstractmethod
    def identity_of(self, aggregate: T) -> Key:
        """This aggregate's key, as a tuple of column values in ``key`` order."""

    @abstractmethod
    def row_of(self, aggregate: T) -> dict[str, Any]:
        """The parent row, key columns included."""

    @abstractmethod
    def restore(self, row: Row[Any], children: Mapping[Table, Sequence[Row[Any]]]) -> T:
        """Rebuild the aggregate from its row and its child rows."""

    def child_rows_of(self, aggregate: T) -> Mapping[Table, Sequence[dict[str, Any]]]:
        """Child rows to write, keyed by table. Empty for an aggregate with no children."""
        return {}

    @property
    def child_tables(self) -> Sequence[tuple[Table, Sequence[str]]]:
        """Child tables to read, each with the columns naming its parent."""
        return ()

    # ---- the port operations ----

    @resilient()
    async def _add(self, aggregate: T) -> None:
        key = self.identity_of(aggregate)
        async with translating(self._describe(key)), self._engine.begin() as conn:
            await conn.execute(insert(self._table).values(**self.row_of(aggregate)))
            await self._write_children(conn, aggregate)
        self._identities[key] = aggregate

    @resilient()
    async def _save(self, aggregate: T) -> None:
        key = self.identity_of(aggregate)
        row = {
            column: value
            for column, value in self.row_of(aggregate).items()
            if column not in self._key_columns
        }
        async with translating(self._describe(key)), self._engine.begin() as conn:
            result = await conn.execute(
                update(self._table).where(self._key_match(key)).values(**row)
            )
            if result.rowcount == 0:
                raise AggregateNotFoundError(f"{self._describe(key)} was never added")
            await self._replace_children(conn, aggregate, key)
        self._identities[key] = aggregate

    @resilient()
    async def _get(self, *key: Any) -> T | None:
        async with translating(self._describe(key)), self._engine.connect() as conn:
            row = (
                await conn.execute(select(self._table).where(self._key_match(key)))
            ).one_or_none()
            if row is None:
                return None
            return await self._materialise(conn, row)

    @resilient()
    async def _find_one(self, whereclause: Any) -> T | None:
        """A lookup by something other than the key — a matric number, a course code."""
        async with translating(self._label), self._engine.connect() as conn:
            row = (await conn.execute(select(self._table).where(whereclause))).one_or_none()
            if row is None:
                return None
            return await self._materialise(conn, row)

    @resilient()
    async def _exists(self, whereclause: Any) -> bool:
        """Whether any row matches. For the questions that are not about an aggregate."""
        async with translating(self._label), self._engine.connect() as conn:
            found = await conn.execute(
                select(self._table.c[self._key_columns[0]]).where(whereclause).limit(1)
            )
            return found.first() is not None

    @resilient()
    async def _list(self, whereclause: Any = None) -> tuple[T, ...]:
        """Every matching aggregate, in the order it was added."""
        statement = select(self._table)
        if whereclause is not None:
            statement = statement.where(whereclause)
        statement = statement.order_by(self._table.c.ordinal)
        async with translating(self._label), self._engine.connect() as conn:
            rows = (await conn.execute(statement)).all()
            return tuple([await self._materialise(conn, row) for row in rows])

    # ---- internals ----

    def _key_of_row(self, row: Row[Any]) -> Key:
        return tuple(getattr(row, column) for column in self._key_columns)

    def _key_match(self, key: Key) -> Any:
        return self._match(self._table, self._key_columns, key)

    @staticmethod
    def _match(table: Table, columns: Sequence[str], key: Key) -> Any:
        """``column = value`` for every part of the key, joined with AND."""
        return and_(
            *(table.c[column] == value for column, value in zip(columns, key, strict=True))
        )

    def _describe(self, key: Key) -> str:
        return f"{self._label} {'/'.join(str(part) for part in key)}"

    def _remember(self, key: Key, aggregate: T) -> T:
        """Register ``aggregate`` unless this repository already holds one for ``key``.

        ``setdefault`` rather than assignment, and there is no ``await`` between the read and
        the write, so concurrent tasks that all missed the map still converge on one instance.
        That is what ``get_or_start`` needs to keep its promise under two hundred callers.
        """
        return self._identities.setdefault(key, aggregate)

    async def _materialise(self, conn: AsyncConnection, row: Row[Any]) -> T:
        """Reconstitute ``row``, then hand back the instance this repository already holds.

        Reconstitution runs either way. Returning the held instance is what preserves the
        identity the in-memory store gave; running the mapping anyway is what stops a
        reconstitution bug from being invisible for as long as the map is warm.
        """
        key = self._key_of_row(row)
        children = {
            table: (
                await conn.execute(select(table).where(self._match(table, parent_columns, key)))
            ).all()
            for table, parent_columns in self.child_tables
        }
        restored = self.restore(row, children)
        return self._identities.get(key, restored)

    async def _write_children(self, conn: AsyncConnection, aggregate: T) -> None:
        for table, rows in self.child_rows_of(aggregate).items():
            if rows:
                await conn.execute(insert(table), [dict(row) for row in rows])

    async def _replace_children(self, conn: AsyncConnection, aggregate: T, key: Key) -> None:
        """Delete and rewrite, rather than diff.

        An aggregate's children have no life outside it, so the set they now are is the whole
        of the truth about them. A diff would be a second opinion about what changed, kept in
        step by hand.
        """
        for table, parent_columns in self.child_tables:
            await conn.execute(delete(table).where(self._match(table, parent_columns, key)))
        await self._write_children(conn, aggregate)

    def forget(self) -> None:
        """Drop the identity map. For a composition root rebuilding its wiring, not for callers."""
        self._identities.clear()
