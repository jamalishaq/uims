"""The in-memory event publisher: publishing means remembering, in order."""

from faculty_department.adapters.outbound import InMemoryEventPublisher
from faculty_department.domain import AcademicYear, GradeSubmitted, SessionOpened

A_GRADE = GradeSubmitted(
    student_id="stu-2026-0001",
    course_id="csc-101",
    semester_id="sem-2026-1",
    grade=68,
)
ANOTHER_GRADE = GradeSubmitted(
    student_id="stu-2026-0002",
    course_id="csc-101",
    semester_id="sem-2026-1",
    grade=41,
)
A_SESSION_OPENING = SessionOpened(session_id="sess-2026", academic_year=AcademicYear(2026))


class TestPublishing:
    def test_a_new_publisher_has_published_nothing(self) -> None:
        assert InMemoryEventPublisher().published == ()

    def test_events_are_kept_in_publication_order(self) -> None:
        publisher = InMemoryEventPublisher()

        publisher.publish(A_SESSION_OPENING)
        publisher.publish(A_GRADE)
        publisher.publish(ANOTHER_GRADE)

        assert publisher.published == (A_SESSION_OPENING, A_GRADE, ANOTHER_GRADE)

    def test_the_same_event_published_twice_is_recorded_twice(self) -> None:
        """The publisher announces; it does not deduplicate. That is a consumer's concern."""
        publisher = InMemoryEventPublisher()

        publisher.publish(A_GRADE)
        publisher.publish(A_GRADE)

        assert publisher.published == (A_GRADE, A_GRADE)

    def test_clear_forgets_what_was_published(self) -> None:
        publisher = InMemoryEventPublisher()
        publisher.publish(A_GRADE)

        publisher.clear()

        assert publisher.published == ()


class TestPublishedIsACopy:
    def test_callers_cannot_rewrite_history(self) -> None:
        publisher = InMemoryEventPublisher()
        publisher.publish(A_GRADE)

        published = publisher.published
        assert isinstance(published, tuple)

        publisher.publish(ANOTHER_GRADE)

        assert published == (A_GRADE,)
        assert publisher.published == (A_GRADE, ANOTHER_GRADE)
