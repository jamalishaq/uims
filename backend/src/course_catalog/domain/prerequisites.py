"""Reading prerequisite chains, and refusing to create circular ones.

A :class:`Course` holds only the ids of the courses immediately before it. The chain —
what CSC301 really depends on, all the way down — spans many aggregates, so it cannot
live on any one of them.

It lives in the domain rather than in a use case because "a course may not, however
indirectly, require itself" is a rule about how a curriculum works, not about how this
system orchestrates a request. Keeping it here is what stops the rule from being
restated slightly differently by the next use case that needs it.

To stay in the domain it must not know what storage looks like, so it is constructed
with a lookup rather than a repository; the application layer passes
``repository.get``. Injecting the accessor as a callable is the same move
``InMemoryStore`` already makes with ``identity``.

**The lookup is awaited, which makes this the one module in any ``domain/`` package that
is asynchronous.** It is not an exception to "the domain does no I/O" so much as the proof
of the rule: every other domain object is handed the aggregates it reasons about, and this
one cannot be, because which courses it needs is the very thing the traversal discovers. A
chain is a walk of unknown depth across many aggregates, so the round trips are inherent
rather than incidental. The alternative — having the application layer pre-load whatever
the walk might reach — means the application layer performing the walk in order to know
what to fetch, which is precisely the restatement of the rule this module exists to
prevent. Nothing else changes: no port, no repository and no storage type appears here,
and the cycle rule is still stated once.
"""

from collections import deque
from collections.abc import Awaitable, Callable

from course_catalog.domain.course import Course
from course_catalog.domain.errors import PrerequisiteCycleError


class PrerequisiteGraph:
    """Transitive prerequisite reading over whatever courses the lookup can reach."""

    def __init__(self, resolve: Callable[[str], Awaitable[Course | None]]) -> None:
        self._resolve = resolve

    async def chain_for(self, course_id: str) -> tuple[str, ...]:
        """Every course required before ``course_id``, directly or not.

        Breadth-first, so the courses taken immediately before come first and the
        distant foundations last. Deduplicated, so a diamond — two second-year courses
        both resting on CSC101 — reports CSC101 once. The starting course is never
        included, even if cyclic data makes it reachable from itself.

        Ids the lookup cannot resolve contribute nothing rather than raising. Whether a
        stored id ought to resolve is a question about what this system holds, and the
        answer to that is the application layer's to give.
        """
        seen = {course_id}
        chain: list[str] = []
        queue = deque(await self._direct_prerequisites(course_id))

        while queue:
            next_id = queue.popleft()
            if next_id in seen:
                continue
            seen.add(next_id)
            chain.append(next_id)
            queue.extend(await self._direct_prerequisites(next_id))

        return tuple(chain)

    async def ensure_can_require(self, course: Course, prerequisite_id: str) -> None:
        """Check that requiring ``prerequisite_id`` would not close a loop.

        Direct self-reference is not checked here: :meth:`Course.add_prerequisite`
        catches that first, without needing a lookup, and says so more precisely.

        Raises:
            PrerequisiteCycleError: the course is already somewhere beneath the
                proposed prerequisite, so the edge would make it require itself.
        """
        if course.course_id in await self.chain_for(prerequisite_id):
            raise PrerequisiteCycleError(
                f"course {course.course_id} cannot require {prerequisite_id}: "
                f"{prerequisite_id} already requires {course.course_id}"
            )

    async def _direct_prerequisites(self, course_id: str) -> tuple[str, ...]:
        course = await self._resolve(course_id)
        return () if course is None else course.prerequisite_ids
