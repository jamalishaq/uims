"""The shared bus: a name, a mapping, and delivery in order.

``src/event_bus.py`` is a flat module for the same reason ``persistence.py`` and
``http_api.py`` are — it holds what has no context in it. What is worth proving about it is
exactly what makes it safe to share: that it never needs to know whose event it is carrying,
that no class crosses it, and that a subscriber's failure is not swallowed.

Its events here are throwaway dataclasses rather than any context's, which is the point: a
bus that could only be tested with a real ``GradeSubmitted`` would be a bus that knew
something about Faculty & Department.
"""

from collections.abc import Mapping
from dataclasses import dataclass

import pytest

from event_bus import EventBus


@dataclass(frozen=True)
class ThingHappened:
    subject: str
    count: int


@dataclass(frozen=True)
class NestedThingHappened:
    subject: str
    detail: ThingHappened


@dataclass(frozen=True)
class OtherThingHappened:
    subject: str


def a_recorder() -> tuple[list[Mapping[str, object]], object]:
    seen: list[Mapping[str, object]] = []

    async def subscriber(payload: Mapping[str, object]) -> None:
        seen.append(payload)

    return seen, subscriber


class TestDelivery:
    async def test_a_published_event_reaches_its_subscriber_as_a_mapping(self) -> None:
        bus = EventBus()
        seen, subscriber = a_recorder()
        bus.subscribe("ThingHappened", subscriber)  # type: ignore[arg-type]

        await bus.publish(ThingHappened(subject="a", count=1))

        assert seen == [{"subject": "a", "count": 1}]

    async def test_no_class_crosses_the_bus(self) -> None:
        """A type is exactly the thing that cannot cross a context boundary."""
        bus = EventBus()
        seen, subscriber = a_recorder()
        bus.subscribe("NestedThingHappened", subscriber)  # type: ignore[arg-type]

        await bus.publish(
            NestedThingHappened(subject="a", detail=ThingHappened(subject="b", count=2))
        )

        (payload,) = seen
        assert payload == {"subject": "a", "detail": {"subject": "b", "count": 2}}
        assert isinstance(payload["detail"], dict)

    async def test_events_are_routed_by_their_class_name(self) -> None:
        bus = EventBus()
        seen, subscriber = a_recorder()
        bus.subscribe("ThingHappened", subscriber)  # type: ignore[arg-type]

        await bus.publish(OtherThingHappened(subject="a"))

        assert seen == []

    async def test_subscribers_are_delivered_to_in_subscription_order(self) -> None:
        bus = EventBus()
        order: list[str] = []

        async def first(payload: Mapping[str, object]) -> None:
            order.append("first")

        async def second(payload: Mapping[str, object]) -> None:
            order.append("second")

        bus.subscribe("ThingHappened", first)
        bus.subscribe("ThingHappened", second)
        await bus.publish(ThingHappened(subject="a", count=1))

        assert order == ["first", "second"]

    async def test_an_event_nobody_subscribed_to_is_not_an_error(self) -> None:
        """The ordinary state of a composition root wired for more than it exercises."""
        bus = EventBus()
        await bus.publish(ThingHappened(subject="a", count=1))
        assert len(bus.published) == 1

    async def test_a_failing_subscriber_takes_the_publish_call_down(self) -> None:
        """Deliberate for an in-memory bus: swallowing it would report an offer as accepted
        that no ledger ever heard about. A real broker retries and dead-letters instead."""
        bus = EventBus()

        async def exploding(payload: Mapping[str, object]) -> None:
            raise RuntimeError("subscriber down")

        bus.subscribe("ThingHappened", exploding)

        with pytest.raises(RuntimeError, match="subscriber down"):
            await bus.publish(ThingHappened(subject="a", count=1))


class TestBookkeeping:
    async def test_published_is_a_copy_callers_cannot_rewrite(self) -> None:
        bus = EventBus()
        await bus.publish(ThingHappened(subject="a", count=1))

        assert isinstance(bus.published, tuple)
        assert len(bus.published) == 1

    def test_subscribers_for_is_a_copy(self) -> None:
        bus = EventBus()
        _, subscriber = a_recorder()
        bus.subscribe("ThingHappened", subscriber)  # type: ignore[arg-type]

        assert len(bus.subscribers_for("ThingHappened")) == 1
        assert bus.subscribers_for("NeverPublished") == ()

    async def test_clear_forgets_history_but_keeps_wiring(self) -> None:
        """Subscriptions are wiring, not history."""
        bus = EventBus()
        _, subscriber = a_recorder()
        bus.subscribe("ThingHappened", subscriber)  # type: ignore[arg-type]
        await bus.publish(ThingHappened(subject="a", count=1))

        bus.clear()

        assert bus.published == ()
        assert len(bus.subscribers_for("ThingHappened")) == 1

    async def test_anything_that_is_not_a_dataclass_is_refused(self) -> None:
        """The one constraint the bus depends on, checked where the message is still useful."""
        bus = EventBus()

        with pytest.raises(TypeError, match="dataclass"):
            await bus.publish({"subject": "a"})

    async def test_a_dataclass_type_is_not_an_event(self) -> None:
        bus = EventBus()

        with pytest.raises(TypeError, match="dataclass"):
            await bus.publish(ThingHappened)
