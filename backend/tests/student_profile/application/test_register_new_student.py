"""``RegisterNewStudent`` driven through its ports — the manual creation path.

Three things are under test that the domain tests cannot see: that the use case asks
Faculty & Department for the format inputs rather than trusting its caller, that the
counter is per department *and* per year, and that a number, once drawn, is never drawn
again — including when several registrations run at once.
"""

import asyncio
from datetime import date

import pytest

from student_profile.adapters.outbound import InMemoryMatricSequenceRepository
from student_profile.application import (
    ProgramPlacementUnknownError,
    RegisterNewStudent,
    RegisterNewStudentCommand,
)
from student_profile.domain import (
    DepartmentCode,
    EntryYear,
    InvalidLevelError,
    Level,
    MatricNumber,
    MissingIdentifierError,
)
from student_profile.ports import DuplicateAggregateError, StudentRepositoryPort

CSC_PROGRAM_ID = "prog-csc-bsc"
MCB_PROGRAM_ID = "prog-mcb-bsc"
SESSION_2026 = "sess-2026"
SESSION_2027 = "sess-2027"


def a_command(**overrides: object) -> RegisterNewStudentCommand:
    fields: dict[str, object] = {
        "student_id": "stu-0001",
        "program_id": CSC_PROGRAM_ID,
        "entry_session_id": SESSION_2026,
        "full_name": "Adaeze Okonkwo",
        "date_of_birth": date(2008, 4, 17),
    }
    fields.update(overrides)
    return RegisterNewStudentCommand(**fields)  # type: ignore[arg-type]


class TestRegisteringOneStudent:
    async def test_the_student_gets_a_matric_number_in_the_lasu_form(
        self, register_new_student: RegisterNewStudent
    ) -> None:
        student = await register_new_student.execute(a_command())

        assert student.matric_number == MatricNumber("260591001")

    async def test_the_student_is_stored_under_their_own_id(
        self, register_new_student: RegisterNewStudent, students: StudentRepositoryPort
    ) -> None:
        student = await register_new_student.execute(a_command())

        assert await students.get("stu-0001") is student

    async def test_the_student_can_be_found_by_the_number_they_will_quote(
        self, register_new_student: RegisterNewStudent, students: StudentRepositoryPort
    ) -> None:
        student = await register_new_student.execute(a_command())

        assert await students.find_by_matric_number(MatricNumber("260591001")) is student

    async def test_the_bio_data_is_assembled_from_the_command(
        self, register_new_student: RegisterNewStudent
    ) -> None:
        student = await register_new_student.execute(
            a_command(email="adaeze@lasu.edu.ng", phone_number="08012345678")
        )

        assert student.bio_data.full_name == "Adaeze Okonkwo"
        assert student.bio_data.date_of_birth == date(2008, 4, 17)
        assert student.bio_data.email == "adaeze@lasu.edu.ng"
        assert student.bio_data.phone_number == "08012345678"

    async def test_a_student_starts_at_100_level_unless_told_otherwise(
        self, register_new_student: RegisterNewStudent
    ) -> None:
        assert (await register_new_student.execute(a_command())).entry_level == Level(100)

    async def test_direct_entry_is_stated_explicitly(
        self, register_new_student: RegisterNewStudent
    ) -> None:
        student = await register_new_student.execute(a_command(entry_level=200))

        assert student.entry_level == Level(200)

    async def test_a_student_registered_by_hand_carries_no_applicant_id(
        self, register_new_student: RegisterNewStudent
    ) -> None:
        assert (await register_new_student.execute(a_command())).applicant_id is None

    async def test_the_counter_is_persisted_through_its_port(
        self,
        register_new_student: RegisterNewStudent,
        sequences: InMemoryMatricSequenceRepository,
    ) -> None:
        await register_new_student.execute(a_command())

        stored = await sequences.get(DepartmentCode("0591"), EntryYear(2026))
        assert stored is not None
        assert stored.issued == 1


class TestSequentialNumbers:
    async def test_two_students_of_one_department_and_year_run_in_sequence(
        self, register_new_student: RegisterNewStudent
    ) -> None:
        first = await register_new_student.execute(a_command(student_id="stu-0001"))
        second = await register_new_student.execute(
            a_command(student_id="stu-0002", full_name="Chidi Nwosu")
        )

        assert (first.matric_number.value, second.matric_number.value) == (
            "260591001",
            "260591002",
        )

    async def test_another_department_in_the_same_year_starts_again_at_one(
        self, register_new_student: RegisterNewStudent
    ) -> None:
        await register_new_student.execute(a_command(student_id="stu-0001"))

        other = await register_new_student.execute(
            a_command(student_id="stu-0002", program_id=MCB_PROGRAM_ID, full_name="Bisi Ade")
        )

        assert other.matric_number == MatricNumber("260672001")

    async def test_the_same_department_in_another_year_starts_again_at_one(
        self, register_new_student: RegisterNewStudent
    ) -> None:
        await register_new_student.execute(a_command(student_id="stu-0001"))

        next_year = await register_new_student.execute(
            a_command(student_id="stu-0002", entry_session_id=SESSION_2027, full_name="Bisi Ade")
        )

        assert next_year.matric_number == MatricNumber("270591001")

    async def test_each_intake_keeps_its_own_counter(
        self,
        register_new_student: RegisterNewStudent,
        sequences: InMemoryMatricSequenceRepository,
    ) -> None:
        for index, program_id in enumerate([CSC_PROGRAM_ID, CSC_PROGRAM_ID, MCB_PROGRAM_ID]):
            await register_new_student.execute(
                a_command(student_id=f"stu-{index}", program_id=program_id)
            )

        assert {sequence.key: sequence.issued for sequence in await sequences.all()} == {
            ("0591", 2026): 2,
            ("0672", 2026): 1,
        }


class TestFactsItRefusesToInvent:
    async def test_an_unknown_program_stops_the_registration(
        self, register_new_student: RegisterNewStudent
    ) -> None:
        """Without a department code there is no number to issue, and guessing one would
        put a student in a department they are not in."""
        with pytest.raises(ProgramPlacementUnknownError):
            await register_new_student.execute(a_command(program_id="prog-nobody"))

    async def test_a_program_outside_the_session_stops_the_registration(
        self, register_new_student: RegisterNewStudent
    ) -> None:
        with pytest.raises(ProgramPlacementUnknownError):
            await register_new_student.execute(
                a_command(program_id=MCB_PROGRAM_ID, entry_session_id=SESSION_2027)
            )

    async def test_nothing_is_stored_when_the_placement_is_unknown(
        self,
        register_new_student: RegisterNewStudent,
        students: StudentRepositoryPort,
        sequences: InMemoryMatricSequenceRepository,
    ) -> None:
        with pytest.raises(ProgramPlacementUnknownError):
            await register_new_student.execute(a_command(program_id="prog-nobody"))

        assert await students.get("stu-0001") is None
        assert await sequences.all() == ()


class TestRejectedCommands:
    """A rejected command must not consume a number. Numbers are not recoverable."""

    async def test_a_blank_name_is_rejected_before_anything_is_claimed(
        self,
        register_new_student: RegisterNewStudent,
        sequences: InMemoryMatricSequenceRepository,
    ) -> None:
        with pytest.raises(MissingIdentifierError):
            await register_new_student.execute(a_command(full_name="   "))

        assert await sequences.all() == ()

    async def test_an_impossible_level_is_rejected_before_anything_is_claimed(
        self,
        register_new_student: RegisterNewStudent,
        sequences: InMemoryMatricSequenceRepository,
    ) -> None:
        with pytest.raises(InvalidLevelError):
            await register_new_student.execute(a_command(entry_level=150))

        assert await sequences.all() == ()

    async def test_a_reused_student_id_is_a_repository_failure(
        self, register_new_student: RegisterNewStudent
    ) -> None:
        await register_new_student.execute(a_command())

        with pytest.raises(DuplicateAggregateError):
            await register_new_student.execute(a_command(full_name="Chidi Nwosu"))

    async def test_a_registration_that_fails_at_the_last_step_burns_its_number(
        self, register_new_student: RegisterNewStudent
    ) -> None:
        """A gap in the sequence, deliberately. The alternative — winding the counter
        back — is what lets a second student be handed the first one's number."""
        await register_new_student.execute(a_command(student_id="stu-0001"))
        with pytest.raises(DuplicateAggregateError):
            await register_new_student.execute(a_command(student_id="stu-0001"))

        third = await register_new_student.execute(a_command(student_id="stu-0003"))
        assert third.matric_number == MatricNumber("260591003")


class TestConcurrentRegistration:
    async def test_simultaneous_registrations_cannot_share_a_matric_number(
        self, register_new_student: RegisterNewStudent
    ) -> None:
        """The end-to-end form of the invariant: many registrations, one intake, no two
        students holding the same number."""
        count = 100

        students = await asyncio.gather(
            *(
                register_new_student.execute(a_command(student_id=f"stu-{index:04d}"))
                for index in range(count)
            )
        )

        issued = {student.matric_number.value for student in students}
        assert len(issued) == count
        assert issued == {f"260591{index:03d}" for index in range(1, count + 1)}

    async def test_simultaneous_registrations_across_intakes_stay_separate(
        self, register_new_student: RegisterNewStudent
    ) -> None:
        """Two departments racing must not be serialised into one counter between them."""
        programs = [CSC_PROGRAM_ID, MCB_PROGRAM_ID]

        students = await asyncio.gather(
            *(
                register_new_student.execute(
                    a_command(student_id=f"stu-{index:04d}", program_id=programs[index % 2])
                )
                for index in range(40)
            )
        )

        csc = {s.matric_number.value for s in students if s.matric_number.value[2:6] == "0591"}
        mcb = {s.matric_number.value for s in students if s.matric_number.value[2:6] == "0672"}
        assert csc == {f"260591{index:03d}" for index in range(1, 21)}
        assert mcb == {f"260672{index:03d}" for index in range(1, 21)}
