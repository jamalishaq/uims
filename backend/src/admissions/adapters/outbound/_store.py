"""The dict behind the in-memory repositories in this package.

A near-copy of Course Catalog's and Faculty & Department's stores, and copied on purpose:
a context may not import another context's code at all (CLAUDE.md section 4), and the
architecture fitness test enforces it. The duplication is the price of the boundary, and
it buys something real — when the Postgres adapters of Phase 6 arrive, "what does ``save``
mean" has exactly one answer per context, and this context is free to answer differently.

Known divergence from a real database, and the reason it is called out here rather than
discovered later: this store holds *live references*. A caller that mutates an aggregate it
fetched sees the change on the next ``get`` whether or not it called ``save``. Under the
Postgres adapters the same code would silently lose the change. Tests that mean to
exercise a write must call ``save`` explicitly rather than lean on this.
"""

from collections.abc import Callable

from admissions.ports.errors import AggregateNotFoundError, DuplicateAggregateError


class InMemoryStore[T]:
    """A dict of identifier to aggregate, with add/save/get/all semantics."""

    def __init__(self, label: str, identity: Callable[[T], str]) -> None:
        self._label = label
        self._identity = identity
        self._items: dict[str, T] = {}

    def add(self, item: T) -> None:
        key = self._identity(item)
        if key in self._items:
            raise DuplicateAggregateError(f"{self._label} {key} is already stored")
        self._items[key] = item

    def save(self, item: T) -> None:
        key = self._identity(item)
        if key not in self._items:
            raise AggregateNotFoundError(f"{self._label} {key} was never added")
        self._items[key] = item

    def get(self, key: str) -> T | None:
        return self._items.get(key)

    def all(self) -> tuple[T, ...]:
        """Everything stored, in insertion order. A tuple: the caller cannot write back."""
        return tuple(self._items.values())
