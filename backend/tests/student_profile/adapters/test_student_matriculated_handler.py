"""The event creation path, and the one claim this phase exists to make good on.

Admissions matriculates an applicant; a student appears here with a matric number. The
thing worth proving is not that the handler works but that it is *not a second way of
issuing a number*: it translates the event and calls the same use case an administrator
calls, so the two paths cannot drift in format or collide on a serial.

The interleaving tests are the ones to read. If the event path ever grew its own issuer
or its own counter, those are the tests that would fail.
"""

import asyncio
from datetime import date

import pytest

from student_profile.adapters.inbound import (
    StudentMatriculatedHandler,
    StudentMatriculatedMessage,
)
from student_profile.adapters.outbound import InMemoryMatricSequenceRepository
from student_profile.application import (
    ProgramPlacementUnknownError,
    RegisterNewStudent,
    RegisterNewStudentCommand,
)
from student_profile.domain import Level, MatricNumber
from student_profile.ports import StudentRepositoryPort

CSC_PROGRAM_ID = "prog-csc-bsc"
MCB_PROGRAM_ID = "prog-mcb-bsc"
SESSION_2026 = "sess-2026"


def a_message(**overrides: object) -> StudentMatriculatedMessage:
    fields: dict[str, object] = {
        "applicant_id": "app-0001",
        "program_id": CSC_PROGRAM_ID,
        "session_id": SESSION_2026,
        "full_name": "Adaeze Okonkwo",
        "date_of_birth": date(2008, 4, 17),
    }
    fields.update(overrides)
    return StudentMatriculatedMessage(**fields)  # type: ignore[arg-type]


def a_manual_command(**overrides: object) -> RegisterNewStudentCommand:
    fields: dict[str, object] = {
        "student_id": "stu-manual-1",
        "program_id": CSC_PROGRAM_ID,
        "entry_session_id": SESSION_2026,
        "full_name": "Chidi Nwosu",
    }
    fields.update(overrides)
    return RegisterNewStudentCommand(**fields)  # type: ignore[arg-type]


class TestTheEventPath:
    async def test_a_matriculated_applicant_becomes_a_student_with_a_matric_number(
        self, matriculation_handler: StudentMatriculatedHandler
    ) -> None:
        student = await matriculation_handler.handle(a_message())

        assert student.matric_number == MatricNumber("260591001")

    async def test_the_student_is_stored(
        self,
        matriculation_handler: StudentMatriculatedHandler,
        students: StudentRepositoryPort,
    ) -> None:
        student = await matriculation_handler.handle(a_message())

        assert await students.get(student.student_id) is student

    async def test_the_student_remembers_which_applicant_they_were(
        self, matriculation_handler: StudentMatriculatedHandler
    ) -> None:
        """Billing's account was opened under that applicant id; this is the link to it."""
        assert (await matriculation_handler.handle(a_message())).applicant_id == "app-0001"

    async def test_the_bio_data_carried_by_the_event_reaches_the_student(
        self, matriculation_handler: StudentMatriculatedHandler
    ) -> None:
        student = await matriculation_handler.handle(
            a_message(email="adaeze@lasu.edu.ng", phone_number="08012345678")
        )

        assert student.bio_data.full_name == "Adaeze Okonkwo"
        assert student.bio_data.date_of_birth == date(2008, 4, 17)
        assert student.bio_data.email == "adaeze@lasu.edu.ng"
        assert student.bio_data.phone_number == "08012345678"

    async def test_the_offered_program_is_the_one_the_student_is_placed_in(
        self, matriculation_handler: StudentMatriculatedHandler
    ) -> None:
        """Admissions may have offered an alternative to what was applied for; the event
        carries the offered program, and nothing here second-guesses it."""
        student = await matriculation_handler.handle(a_message(program_id=MCB_PROGRAM_ID))

        assert student.program_id == MCB_PROGRAM_ID
        assert student.matric_number == MatricNumber("260672001")

    async def test_a_matriculated_student_starts_at_100_level_unless_the_event_says_otherwise(
        self, matriculation_handler: StudentMatriculatedHandler
    ) -> None:
        assert (await matriculation_handler.handle(a_message())).entry_level == Level(100)
        assert (
            await matriculation_handler.handle(a_message(applicant_id="app-0002", entry_level=200))
        ).entry_level == Level(200)

    async def test_the_student_id_is_this_context_s_to_mint(
        self, matriculation_handler: StudentMatriculatedHandler
    ) -> None:
        """It is not the applicant id and not the matric number: Admissions does not name
        our aggregate, and the matric number is not known until the use case runs."""
        student = await matriculation_handler.handle(a_message())

        assert student.student_id not in {"app-0001", student.matric_number.value}
        assert student.student_id

    async def test_an_injected_id_source_is_used_when_one_is_given(
        self, register_new_student: RegisterNewStudent, students: StudentRepositoryPort
    ) -> None:
        handler = StudentMatriculatedHandler(
            register_new_student=register_new_student,
            students=students,
            new_student_id=lambda: "stu-injected",
        )

        assert (await handler.handle(a_message())).student_id == "stu-injected"

    async def test_an_unknown_program_stops_the_matriculation(
        self, matriculation_handler: StudentMatriculatedHandler
    ) -> None:
        with pytest.raises(ProgramPlacementUnknownError):
            await matriculation_handler.handle(a_message(program_id="prog-nobody"))


class TestRedelivery:
    """At-least-once delivery is normal. Two matric numbers for one applicant is not."""

    async def test_the_same_event_twice_produces_one_student(
        self, matriculation_handler: StudentMatriculatedHandler
    ) -> None:
        first = await matriculation_handler.handle(a_message())
        second = await matriculation_handler.handle(a_message())

        assert second is first

    async def test_a_redelivery_consumes_no_matric_number(
        self,
        matriculation_handler: StudentMatriculatedHandler,
        sequences: InMemoryMatricSequenceRepository,
    ) -> None:
        await matriculation_handler.handle(a_message())
        await matriculation_handler.handle(a_message())

        assert [sequence.issued for sequence in await sequences.all()] == [1]

    async def test_a_redelivery_does_not_displace_the_next_applicant(
        self, matriculation_handler: StudentMatriculatedHandler
    ) -> None:
        await matriculation_handler.handle(a_message(applicant_id="app-0001"))
        await matriculation_handler.handle(a_message(applicant_id="app-0001"))

        next_student = await matriculation_handler.handle(a_message(applicant_id="app-0002"))
        assert next_student.matric_number == MatricNumber("260591002")

    async def test_two_different_applicants_are_two_students(
        self, matriculation_handler: StudentMatriculatedHandler
    ) -> None:
        first = await matriculation_handler.handle(a_message(applicant_id="app-0001"))
        second = await matriculation_handler.handle(a_message(applicant_id="app-0002"))

        assert first is not second
        assert first.matric_number != second.matric_number


class TestBothPathsShareOneIssuer:
    """The requirement this phase turns on, stated four ways."""

    async def test_both_paths_produce_the_same_shape_of_number(
        self,
        matriculation_handler: StudentMatriculatedHandler,
        register_new_student: RegisterNewStudent,
    ) -> None:
        by_event = await matriculation_handler.handle(a_message())
        by_hand = await register_new_student.execute(a_manual_command())

        assert by_event.matric_number.value[:6] == by_hand.matric_number.value[:6]
        assert len(by_event.matric_number.value) == len(by_hand.matric_number.value)

    async def test_the_two_paths_continue_one_sequence(
        self,
        matriculation_handler: StudentMatriculatedHandler,
        register_new_student: RegisterNewStudent,
    ) -> None:
        """Interleaved deliberately: a second counter behind either path would show up
        here as a repeated ordinal."""
        issued = [
            (await matriculation_handler.handle(a_message(applicant_id="app-0001"))).matric_number,
            (
                await register_new_student.execute(a_manual_command(student_id="stu-1"))
            ).matric_number,
            (await matriculation_handler.handle(a_message(applicant_id="app-0002"))).matric_number,
            (
                await register_new_student.execute(a_manual_command(student_id="stu-2"))
            ).matric_number,
        ]

        assert [number.value for number in issued] == [
            "260591001",
            "260591002",
            "260591003",
            "260591004",
        ]

    async def test_the_paths_share_one_counter_per_intake(
        self,
        matriculation_handler: StudentMatriculatedHandler,
        register_new_student: RegisterNewStudent,
        sequences: InMemoryMatricSequenceRepository,
    ) -> None:
        await matriculation_handler.handle(a_message())
        await register_new_student.execute(a_manual_command())

        assert {sequence.key: sequence.issued for sequence in await sequences.all()} == {
            ("0591", 2026): 2
        }

    async def test_the_two_paths_racing_cannot_duplicate_a_number(
        self,
        matriculation_handler: StudentMatriculatedHandler,
        register_new_student: RegisterNewStudent,
    ) -> None:
        """The realistic failure: a bulk matriculation running while a registrar types."""
        count = 60

        async def create(index: int) -> str:
            if index % 2:
                return (
                    await matriculation_handler.handle(a_message(applicant_id=f"app-{index:04d}"))
                ).matric_number.value
            return (
                await register_new_student.execute(a_manual_command(student_id=f"stu-{index:04d}"))
            ).matric_number.value

        issued = await asyncio.gather(*(create(index) for index in range(count)))

        assert len(set(issued)) == count
        assert set(issued) == {f"260591{index:03d}" for index in range(1, count + 1)}
