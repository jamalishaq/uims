"""``GradeSubmitted`` from Faculty & Department to Academic Records, over the real bus.

The build playbook's Phase 4.2 verification: "GradeSubmitted → record exists". This module
is the only place in the repository that exercises both contexts at once, and it is a test
rather than production code for the reason the dependency rule gives — neither context may
import the other, so the introduction has to be made by somebody outside both. The
composition root doing it is ``tests/academic_records/conftest.py``; here it is used.

Nothing is stubbed between the two ends. A lecturer submits a grade through Faculty &
Department's real ``SubmitGrade``, against its real ``Lecturer`` and ``Session``
aggregates, publishing through :class:`InMemoryEventBus`, which serialises the event and
hands the payload to Academic Records' real handler, use case, aggregate and repository. The
only thing that is not real is the transport, and Phase 6 replaces that alone.

The three scenarios are the ones the wiring can get wrong: a valid submission must arrive,
a submission the domain rejected must not, and a redelivery must not arrive twice.
"""

from collections.abc import Mapping

import pytest

from academic_records.adapters.outbound import InMemoryCourseCreditAdapter
from academic_records.application import CourseCreditsUnavailableError
from academic_records.ports import AcademicRecordRepositoryPort
from faculty_department.adapters.outbound import (
    InMemoryEventBus,
    InMemoryLecturerRepository,
    InMemorySessionRepository,
)
from faculty_department.application import SubmitGrade, SubmitGradeCommand
from faculty_department.domain import (
    AcademicYear,
    GradeSubmitted,
    Lecturer,
    LecturerNotAssignedToCourseError,
    Semester,
    SemesterOrdinal,
    Session,
)
from faculty_department.ports import LecturerRepositoryPort, SessionRepositoryPort

SESSION_ID = "sess-2026"
FIRST_SEMESTER_ID = "sem-2026-1"
SECOND_SEMESTER_ID = "sem-2026-2"
LECTURER_ID = "lec-001"
DEPARTMENT_ID = "dept-csc"
COURSE_ID = "CSC101"
UNTAUGHT_COURSE_ID = "PHY101"
UNCATALOGUED_COURSE_ID = "CSC299"
STUDENT_ID = "stu-2026-0001"


@pytest.fixture
async def lecturers() -> LecturerRepositoryPort:
    """Faculty & Department's own repositories, built here because this test spans two contexts.

    The Faculty & Department conftest is not in scope for this package, and importing its
    fixtures would couple two test suites that are otherwise independent.

    The lecturer teaches two courses and only one of them is in the catalog, which is how
    the "unknown course" case below reaches Academic Records at all.
    """
    lecturers = InMemoryLecturerRepository()
    lecturer = Lecturer(LECTURER_ID, DEPARTMENT_ID, "Dr Adaeze Okonkwo")
    lecturer.assign_to_course(COURSE_ID, SESSION_ID)
    lecturer.assign_to_course(UNCATALOGUED_COURSE_ID, SESSION_ID)
    await lecturers.add(lecturer)
    return lecturers


@pytest.fixture
async def sessions() -> SessionRepositoryPort:
    sessions = InMemorySessionRepository()
    session = Session.plan(
        SESSION_ID,
        AcademicYear(2026),
        [
            Semester(FIRST_SEMESTER_ID, SemesterOrdinal.FIRST),
            Semester(SECOND_SEMESTER_ID, SemesterOrdinal.SECOND),
        ],
    )
    session.open()
    await sessions.add(session)
    return sessions


@pytest.fixture
def submit_grade(
    lecturers: LecturerRepositoryPort,
    sessions: SessionRepositoryPort,
    wired_bus: InMemoryEventBus,
) -> SubmitGrade:
    """Faculty & Department's use case, publishing into the bus Academic Records listens on.

    ``SubmitGrade`` is constructed exactly as its own tests construct it. It takes an
    ``EventPublisherPort`` and cannot tell that this one delivers.
    """
    return SubmitGrade(lecturers=lecturers, sessions=sessions, events=wired_bus)


@pytest.fixture(autouse=True)
def catalog(courses: InMemoryCourseCreditAdapter) -> None:
    """What Course Catalog would answer on Academic Records' side of the wire."""
    courses.register(COURSE_ID, credit_units=3)


def a_command(**overrides: object) -> SubmitGradeCommand:
    fields: dict[str, object] = {
        "lecturer_id": LECTURER_ID,
        "session_id": SESSION_ID,
        "student_id": STUDENT_ID,
        "course_id": COURSE_ID,
        "semester_id": FIRST_SEMESTER_ID,
        "score": 68,
    }
    fields.update(overrides)
    return SubmitGradeCommand(**fields)  # type: ignore[arg-type]


# ---- the path the phase exists to build ----


async def test_a_submitted_grade_becomes_an_academic_record(
    submit_grade: SubmitGrade, records: AcademicRecordRepositoryPort
) -> None:
    """The whole phase in one assertion: a lecturer submits, and a record exists."""
    assert await records.get(STUDENT_ID) is None

    await submit_grade.execute(a_command())

    record = await records.get(STUDENT_ID)
    assert record is not None
    (line,) = record.grades
    assert (line.course_id, line.semester_id, line.score) == (COURSE_ID, FIRST_SEMESTER_ID, 68)


async def test_the_grade_is_graded_on_academic_records_scale(
    submit_grade: SubmitGrade, records: AcademicRecordRepositoryPort
) -> None:
    """68 is a B worth 4.0 — a fact Faculty & Department published no opinion about."""
    await submit_grade.execute(a_command())

    (line,) = (await records.get(STUDENT_ID)).grades  # type: ignore[union-attr]
    assert (line.letter, str(line.grade_point)) == ("B", "4.0")
    assert line.credit_units == 3


async def test_grades_across_two_semesters_build_one_record(
    submit_grade: SubmitGrade, records: AcademicRecordRepositoryPort
) -> None:
    await submit_grade.execute(a_command(score=75))
    await submit_grade.execute(a_command(semester_id=SECOND_SEMESTER_ID, score=55))

    record = await records.get(STUDENT_ID)
    assert record is not None
    assert record.transcript().semester_ids == (FIRST_SEMESTER_ID, SECOND_SEMESTER_ID)
    assert str(record.cgpa) == "4.00"  # (15.0 + 9.0) / 6


# ---- what must not arrive ----


async def test_a_submission_the_domain_rejected_reaches_nobody(
    submit_grade: SubmitGrade,
    records: AcademicRecordRepositoryPort,
    wired_bus: InMemoryEventBus,
) -> None:
    """An unassigned lecturer's grade is refused before publication, so no record is created."""
    with pytest.raises(LecturerNotAssignedToCourseError):
        await submit_grade.execute(a_command(course_id=UNTAUGHT_COURSE_ID))

    assert wired_bus.published == ()
    assert await records.get(STUDENT_ID) is None


async def test_a_replayed_delivery_leaves_exactly_one_line(
    submit_grade: SubmitGrade, records: AcademicRecordRepositoryPort, wired_bus: InMemoryEventBus
) -> None:
    """At-least-once delivery replayed by hand: the same payload dispatched twice."""
    await submit_grade.execute(a_command())
    published = wired_bus.published[0]
    assert isinstance(published, GradeSubmitted)

    await wired_bus.publish(published)

    record = await records.get(STUDENT_ID)
    assert record is not None
    assert len(record.grades) == 1


async def test_a_grade_for_a_course_the_catalog_does_not_know_fails_the_publish(
    submit_grade: SubmitGrade, records: AcademicRecordRepositoryPort
) -> None:
    """Synchronous delivery means a subscriber's refusal surfaces at the publisher.

    The lecturer teaches ``CSC299`` and Faculty & Department is satisfied; Course Catalog
    has never heard of it, so Academic Records has no weight to record the line at and
    refuses. The failure travels back up the publish call.

    Deliberate for an in-memory bus: swallowing it would report a grade as published that no
    record ever received. A real broker retries and dead-letters instead, and that is what
    Phase 6 buys when this bus is replaced.
    """
    with pytest.raises(CourseCreditsUnavailableError, match=UNCATALOGUED_COURSE_ID):
        await submit_grade.execute(a_command(course_id=UNCATALOGUED_COURSE_ID))

    assert await records.get(STUDENT_ID) is None


# ---- the boundary the wiring must not cross ----


async def test_what_crosses_the_bus_is_plain_data(wired_bus: InMemoryEventBus) -> None:
    """No class from either context travels: the payload is a mapping of primitives.

    This is what ``faculty_department.domain.events`` means by "consumers never import
    these classes; an outbound adapter serialises them at the boundary", and it is why the
    consumer's message type can be its own.
    """
    seen: list[object] = []

    async def watching(payload: Mapping[str, object]) -> None:
        seen.append(payload)

    wired_bus.subscribe("GradeSubmitted", watching)
    await wired_bus.publish(
        GradeSubmitted(
            student_id=STUDENT_ID, course_id=COURSE_ID, semester_id=FIRST_SEMESTER_ID, grade=68
        )
    )

    (payload,) = seen
    assert payload == {
        "student_id": STUDENT_ID,
        "course_id": COURSE_ID,
        "semester_id": FIRST_SEMESTER_ID,
        "grade": 68,
    }
    assert all(isinstance(value, str | int) for value in payload.values())  # type: ignore[attr-defined]


def test_the_wiring_names_the_event_by_string_rather_than_by_type(
    wired_bus: InMemoryEventBus,
) -> None:
    """A type is exactly the thing that cannot cross a context boundary."""
    assert wired_bus.subscribers_for("GradeSubmitted")
    assert wired_bus.subscribers_for("SessionOpened") == ()
