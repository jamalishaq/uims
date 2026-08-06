"""The in-memory event bus, shared by every context that publishes.

A flat module rather than a package, for ``persistence.py``'s and ``http_api.py``'s reason:
``discover_contexts()`` finds contexts by looking for directories under ``src/`` with an
``__init__.py``, so a package here would become an eighth context and break the
``EXPECTED_CONTEXTS`` assertion. Like those two, it holds what has no context in it.

**Why this moved out of Faculty & Department.** ``InMemoryEventBus`` was written there when
that context was the only publisher. It is now one of three: Admissions announces
``OfferAccepted`` and ``StudentMatriculated``, and Billing announces ``AcceptanceFeePaid``
to Admissions. No context may import another (``tests/architecture/test_dependency_rule.py``
rule (b)), so the alternative to this module is three near-identical copies of a class whose
entire body is a dictionary of lists — and three chances for them to disagree about what a
topic name is.

**It imports no context, which is what makes it flat rather than an eighth one.** It never
sees a ``DomainEvent`` of anybody's: it takes a frozen dataclass, reads its class name for a
topic and :func:`dataclasses.asdict` for a payload, and hands the result to whoever
subscribed. Each context keeps its own ``EventPublisherPort`` and a small adapter behind it
that delegates here — so the port stays typed in that context's own events and the machinery
is written once.

**The envelope is a name and a mapping.** A string topic rather than a type, because a type
is exactly the thing that cannot cross a context boundary. Subscribing is
``bus.subscribe("GradeSubmitted", handler)``, and neither side imports the other — which is
the whole reason the wiring can live in a composition root that imports both.

**What crosses is plain data.** Every event is a frozen dataclass and ``asdict`` turns one
into nested dicts of primitives before any subscriber sees it. That is the same
serialisation a real broker would do, so a subscriber written against this bus is written
against the wire format rather than against Python objects that happen to be in the same
process. ``SessionOpened`` carries an ``AcademicYear`` and ``StudentMatriculated`` a
``BioData``; a consumer receiving either class would be holding a piece of somebody else's
domain.

Delivery is sequential, in subscription order, awaited in the publisher's own coroutine —
not fanned out with ``gather``. A subscriber that raises takes the publish call down with
it, and that is deliberate for an in-memory bus: swallowing the failure would report an
offer as accepted that no ledger ever heard about, and concurrent delivery would leave the
publisher unable to say which subscriber failed first. A real broker retries and
dead-letters instead, and *that* is the behaviour replacing this class buys.
"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, is_dataclass
from typing import Any

Subscriber = Callable[[Mapping[str, object]], Awaitable[None]]
"""What a listener looks like from here: something that takes a payload and returns nothing.

Deliberately not a type from any context. A bus that spoke in domain types would be a bus
only one context could publish to and only a context importing it could subscribe to.

Awaitable, because a subscriber that records a grade reaches a repository to do it, and
every repository port in this system is asynchronous. The bus still knows nothing about who
listens or what they do — only that doing it may take a turn of the event loop.
"""


class EventBus:
    """Publishes by delivering to whoever subscribed, and remembers what it published.

    ``Any`` for the event type, and it is not laziness: this class is the one place in
    ``src/`` that must be able to carry *every* context's events without naming one. The
    constraint it does enforce is the one it depends on — a frozen dataclass, checked at
    publish time, because :func:`dataclasses.asdict` is what turns an event into a payload
    and anything else would fail deeper in with a worse message.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Subscriber]] = {}
        self._published: list[Any] = []

    def subscribe(self, event_name: str, subscriber: Subscriber) -> None:
        """Register ``subscriber`` for events published under ``event_name``.

        The name is the event class's own (``"GradeSubmitted"``), matched exactly. A
        subscriber for an event nobody publishes is not an error — it is the ordinary state
        of a composition root wired for more than it happens to exercise.
        """
        self._subscribers.setdefault(event_name, []).append(subscriber)

    async def publish(self, event: Any) -> None:
        """Serialise ``event`` and hand it to every subscriber, in subscription order."""
        if not is_dataclass(event) or isinstance(event, type):
            raise TypeError(
                f"{type(event).__name__} is not a dataclass instance; the bus serialises "
                "events with dataclasses.asdict and cannot carry anything else"
            )
        self._published.append(event)
        payload = asdict(event)
        for subscriber in self._subscribers.get(type(event).__name__, ()):
            await subscriber(payload)

    @property
    def published(self) -> tuple[Any, ...]:
        """What has been published so far. A copy: callers cannot rewrite history."""
        return tuple(self._published)

    def subscribers_for(self, event_name: str) -> tuple[Subscriber, ...]:
        """Who is listening for one event. A copy, so the registry cannot be edited in place."""
        return tuple(self._subscribers.get(event_name, ()))

    def clear(self) -> None:
        """Forget what was published. Subscriptions survive — they are wiring, not history."""
        self._published.clear()


__all__ = ["EventBus", "Subscriber"]
