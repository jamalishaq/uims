"""In-memory ``EventPublisherPort`` that actually delivers: publishing means dispatching.

The successor :class:`InMemoryEventPublisher` promised — "Phase 4.2 introduces the bus that
carries ``GradeSubmitted`` to Academic Records, and it arrives as a different adapter behind
this same port". ``SubmitGrade`` does not change, does not know it is being listened to, and
could not name a subscriber if it wanted to: the port is "deliberately ignorant of who
listens", and a bus that made the publisher aware of its audience would have thrown that away
to save a line of wiring.

**The machinery moved out from under this class and its behaviour did not change.** Topics,
serialisation and ordered delivery now live in ``src/event_bus.py``, a flat module no context
owns, because this context stopped being the only publisher: Admissions announces
``OfferAccepted`` and ``StudentMatriculated``, and Billing announces ``AcceptanceFeePaid``.
No context may import another (rule (b)), so the alternative was three copies of one
dictionary of lists. What is left here is the ten lines that make the shared bus satisfy
*this* context's port with *this* context's event type.

``bus`` is a constructor argument so the composition root can hand every context the same
one. Left to itself this class still builds its own, which is what every test that only
cares about Faculty & Department wants.

The behaviour the flat module documents at length is unchanged and still load-bearing: the
envelope is a name and a mapping so no type crosses a boundary, what crosses is
:func:`dataclasses.asdict` output so ``SessionOpened``'s ``AcademicYear`` never reaches a
subscriber as a class, and delivery is sequential in subscription order with a failing
subscriber taking the publish call down with it.
"""

from event_bus import EventBus, Subscriber
from faculty_department.domain.events import DomainEvent
from faculty_department.ports.event_publisher import EventPublisherPort


class InMemoryEventBus(EventPublisherPort):
    """Publishes by delivering to whoever subscribed, and remembers what it published."""

    def __init__(self, bus: EventBus | None = None) -> None:
        self._bus = bus if bus is not None else EventBus()

    def subscribe(self, event_name: str, subscriber: Subscriber) -> None:
        """Register ``subscriber`` for events published under ``event_name``.

        The name is the event class's own (``"GradeSubmitted"``), matched exactly. A
        subscriber for an event nobody publishes is not an error — it is the ordinary state
        of a composition root wired for more than it happens to exercise.
        """
        self._bus.subscribe(event_name, subscriber)

    async def publish(self, event: DomainEvent) -> None:
        """Serialise ``event`` and hand it to every subscriber, in subscription order."""
        await self._bus.publish(event)

    @property
    def published(self) -> tuple[DomainEvent, ...]:
        """What has been published so far. A copy: callers cannot rewrite history."""
        return self._bus.published

    def subscribers_for(self, event_name: str) -> tuple[Subscriber, ...]:
        """Who is listening for one event. A copy, so the registry cannot be edited in place."""
        return self._bus.subscribers_for(event_name)

    def clear(self) -> None:
        """Forget what was published. Subscriptions survive — they are wiring, not history."""
        self._bus.clear()


__all__ = ["InMemoryEventBus", "Subscriber"]
