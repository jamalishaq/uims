"""In-memory ``EventPublisherPort`` that actually delivers: publishing means dispatching.

The successor :class:`InMemoryEventPublisher` promised — "Phase 4.2 introduces the bus that
carries ``GradeSubmitted`` to Academic Records, and it arrives as a different adapter behind
this same port". This is that adapter. ``SubmitGrade`` does not change, does not know it is
being listened to, and could not name a subscriber if it wanted to: the port is
"deliberately ignorant of who listens", and a bus that made the publisher aware of its
audience would have thrown that away to save a line of wiring.

**What crosses the bus is plain data.** Every event is a frozen dataclass, and
:func:`dataclasses.asdict` turns one into nested dicts of primitives before any subscriber
sees it. That is what ``faculty_department.domain.events`` means by "consumers never import
these classes; an outbound adapter serialises them at the boundary" — and it is the same
serialisation a real broker would do, so a subscriber written against this bus is written
against the wire format rather than against Python objects that happen to be in the same
process. ``SessionOpened`` carries an ``AcademicYear``, and a consumer receiving that class
would be holding a piece of this context's domain.

**The envelope is a name and a mapping.** A string topic rather than a type, because a type
is exactly the thing that cannot cross a context boundary. Subscribing is therefore
``bus.subscribe("GradeSubmitted", handler)``, and neither side imports the other — which is
the whole reason the wiring can live in a composition root that imports both.

Delivery is sequential, in subscription order, awaited in the publisher's own coroutine —
not fanned out with ``gather``. A subscriber that raises takes the publish call down with
it, and that is deliberate for an in-memory bus: swallowing the failure would report a
grade as published that no record ever received, and concurrent delivery would leave the
publisher unable to say which subscriber failed first. A real broker retries and
dead-letters instead, and *that* is the behaviour Phase 6 buys when this class is replaced.
"""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict

from faculty_department.domain.events import DomainEvent
from faculty_department.ports.event_publisher import EventPublisherPort

Subscriber = Callable[[Mapping[str, object]], Awaitable[None]]
"""What a listener looks like from here: something that takes a payload and returns nothing.

Deliberately not a type from any context. A bus that spoke in domain types would be a bus
only this context could publish to and only a context importing it could subscribe to.

Awaitable, because a subscriber that records a grade reaches a repository to do it, and
every repository port in this system is asynchronous. The bus still knows nothing about who
listens or what they do — only that doing it may take a turn of the event loop.
"""


class InMemoryEventBus(EventPublisherPort):
    """Publishes by delivering to whoever subscribed, and remembers what it published."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Subscriber]] = {}
        self._published: list[DomainEvent] = []

    def subscribe(self, event_name: str, subscriber: Subscriber) -> None:
        """Register ``subscriber`` for events published under ``event_name``.

        The name is the event class's own (``"GradeSubmitted"``), matched exactly. A
        subscriber for an event nobody publishes is not an error — it is the ordinary state
        of a composition root wired for more than it happens to exercise.
        """
        self._subscribers.setdefault(event_name, []).append(subscriber)

    async def publish(self, event: DomainEvent) -> None:
        """Serialise ``event`` and hand it to every subscriber, in subscription order."""
        self._published.append(event)
        payload = asdict(event)
        for subscriber in self._subscribers.get(type(event).__name__, ()):
            await subscriber(payload)

    @property
    def published(self) -> tuple[DomainEvent, ...]:
        """What has been published so far. A copy: callers cannot rewrite history."""
        return tuple(self._published)

    def subscribers_for(self, event_name: str) -> tuple[Subscriber, ...]:
        """Who is listening for one event. A copy, so the registry cannot be edited in place."""
        return tuple(self._subscribers.get(event_name, ()))

    def clear(self) -> None:
        """Forget what was published. Subscriptions survive — they are wiring, not history."""
        self._published.clear()
