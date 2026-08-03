"""``InMemoryEventBus``: the ``EventPublisherPort`` that actually delivers.

Tested on its own, with no consumer in sight, because everything worth pinning about it is
true regardless of who subscribes: that a publisher cannot tell it apart from the
remember-only publisher, that what reaches a subscriber is plain data rather than a class
from this context's domain, and that a subscriber's failure is not swallowed.

``tests/academic_records/test_grade_submitted_wiring.py`` is the other half — this bus with
Academic Records on the end of it.
"""

from collections.abc import Mapping
from dataclasses import FrozenInstanceError

import pytest

from faculty_department.adapters.outbound import InMemoryEventBus, Subscriber
from faculty_department.domain import AcademicYear, GradeSubmitted, SessionOpened
from faculty_department.ports import EventPublisherPort

STUDENT_ID = "stu-2026-0001"
COURSE_ID = "CSC101"
SEMESTER_ID = "sem-2026-1"


def a_grade(**overrides: object) -> GradeSubmitted:
    fields: dict[str, object] = {
        "student_id": STUDENT_ID,
        "course_id": COURSE_ID,
        "semester_id": SEMESTER_ID,
        "grade": 68,
    }
    fields.update(overrides)
    return GradeSubmitted(**fields)  # type: ignore[arg-type]


def recording(into: list[object]) -> Subscriber:
    """A subscriber that appends whatever it is handed.

    A coroutine rather than ``list.append`` itself, because a real subscriber reaches a
    repository and every repository port here is asynchronous. What is being tested is
    unchanged: which payloads arrive, and in what order.
    """

    async def subscriber(payload: Mapping[str, object]) -> None:
        into.append(payload)

    return subscriber


def noting(into: list[str], mark: str) -> Subscriber:
    """A subscriber that records only that it ran, for the ordering test."""

    async def subscriber(_: Mapping[str, object]) -> None:
        into.append(mark)

    return subscriber


@pytest.fixture
def bus() -> InMemoryEventBus:
    return InMemoryEventBus()


def test_the_bus_is_an_event_publisher_port(bus: InMemoryEventBus) -> None:
    """The whole point of the design: it swaps in wherever the remember-only one was."""
    assert isinstance(bus, EventPublisherPort)


async def test_a_subscriber_receives_what_is_published(bus: InMemoryEventBus) -> None:
    received: list[object] = []
    bus.subscribe("GradeSubmitted", recording(received))

    await bus.publish(a_grade())

    assert received == [
        {
            "student_id": STUDENT_ID,
            "course_id": COURSE_ID,
            "semester_id": SEMESTER_ID,
            "grade": 68,
        }
    ]


async def test_what_a_subscriber_receives_is_plain_data_and_not_a_domain_class(
    bus: InMemoryEventBus,
) -> None:
    """``SessionOpened`` carries an ``AcademicYear``, and a consumer holding one would be
    holding a piece of this context's domain. The bus serialises before dispatching, which
    is what a real broker would do and what the events module promises.
    """
    received: list[object] = []
    bus.subscribe("SessionOpened", recording(received))

    await bus.publish(SessionOpened(session_id="sess-2026", academic_year=AcademicYear(2026)))

    (payload,) = received
    assert payload == {"session_id": "sess-2026", "academic_year": {"start_year": 2026}}
    assert not isinstance(payload["academic_year"], AcademicYear)  # type: ignore[index]


async def test_publishing_with_nobody_listening_is_fine(bus: InMemoryEventBus) -> None:
    """The port is 'deliberately ignorant of who listens', including of whether anybody does."""
    await bus.publish(a_grade())
    assert len(bus.published) == 1


async def test_a_subscriber_hears_only_the_event_it_subscribed_to(bus: InMemoryEventBus) -> None:
    grades: list[object] = []
    sessions: list[object] = []
    bus.subscribe("GradeSubmitted", recording(grades))
    bus.subscribe("SessionOpened", recording(sessions))

    await bus.publish(a_grade())

    assert len(grades) == 1
    assert sessions == []


async def test_every_subscriber_to_an_event_hears_it_in_subscription_order(
    bus: InMemoryEventBus,
) -> None:
    order: list[str] = []
    bus.subscribe("GradeSubmitted", noting(order, "first"))
    bus.subscribe("GradeSubmitted", noting(order, "second"))

    await bus.publish(a_grade())

    assert order == ["first", "second"]


async def test_the_bus_remembers_what_it_published(bus: InMemoryEventBus) -> None:
    """It is still usable as the spy the remember-only publisher was."""
    await bus.publish(a_grade())
    await bus.publish(a_grade(grade=75))

    assert [event.grade for event in bus.published] == [68, 75]  # type: ignore[union-attr]


async def test_what_it_published_comes_back_as_a_tuple(bus: InMemoryEventBus) -> None:
    await bus.publish(a_grade())
    assert isinstance(bus.published, tuple)


async def test_clearing_forgets_history_but_keeps_the_wiring(bus: InMemoryEventBus) -> None:
    received: list[object] = []
    bus.subscribe("GradeSubmitted", recording(received))
    await bus.publish(a_grade())

    bus.clear()

    assert bus.published == ()
    await bus.publish(a_grade())
    assert len(received) == 2


def test_subscribers_for_reports_the_wiring_without_exposing_it(
    bus: InMemoryEventBus,
) -> None:
    bus.subscribe("GradeSubmitted", lambda _: None)
    assert len(bus.subscribers_for("GradeSubmitted")) == 1
    assert bus.subscribers_for("SessionOpened") == ()
    assert isinstance(bus.subscribers_for("GradeSubmitted"), tuple)


async def test_a_subscriber_that_raises_takes_the_publish_down_with_it(
    bus: InMemoryEventBus,
) -> None:
    """Deliberate. Swallowing it would report an event as published that nobody received."""

    async def refuse(_: Mapping[str, object]) -> None:
        raise RuntimeError("the consumer could not handle it")

    bus.subscribe("GradeSubmitted", refuse)

    with pytest.raises(RuntimeError, match="could not handle it"):
        await bus.publish(a_grade())


def test_an_event_is_immutable_so_the_bus_cannot_alter_it_in_flight(
    bus: InMemoryEventBus,
) -> None:
    event = a_grade()
    with pytest.raises(FrozenInstanceError):
        event.grade = 30  # type: ignore[misc]
