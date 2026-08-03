"""The in-memory adapters, tested against the contracts their ports state.

Phase 6 replaces both with Postgres. These tests are the description of what the
replacements have to do — including the parts that are easy to get subtly different, like
whether ``save`` on something never added is a failure or a silent insert.
"""

import asyncio
from datetime import date

import pytest

from student_profile.adapters.outbound import InMemoryMatricSequenceRepository
from student_profile.domain import (
    BioData,
    DepartmentCode,
    EntryYear,
    Level,
    MatricNumber,
    MatricSequence,
    Student,
)
from student_profile.ports import (
    AggregateNotFoundError,
    DuplicateAggregateError,
    MatricSequenceRepositoryPort,
    StudentRepositoryPort,
)

CSC = DepartmentCode("0591")
MCB = DepartmentCode("0672")
YEAR_2026 = EntryYear(2026)


def a_student(
    student_id: str = "stu-0001", matric: str = "260591001", **overrides: object
) -> Student:
    fields: dict[str, object] = {
        "student_id": student_id,
        "matric_number": MatricNumber(matric),
        "bio_data": BioData(full_name="Adaeze Okonkwo", date_of_birth=date(2008, 4, 17)),
        "program_id": "prog-csc-bsc",
        "entry_session_id": "sess-2026",
        "entry_level": Level(100),
    }
    fields.update(overrides)
    return Student(**fields)  # type: ignore[arg-type]


class TestStudentRepository:
    async def test_a_stored_student_comes_back_by_id(self, students: StudentRepositoryPort) -> None:
        student = a_student()
        await students.add(student)

        assert await students.get("stu-0001") is student

    async def test_an_unknown_id_is_not_an_error(self, students: StudentRepositoryPort) -> None:
        """Not finding somebody you asked about is a normal answer, not a failure."""
        assert await students.get("stu-nobody") is None

    async def test_the_same_id_cannot_be_added_twice(self, students: StudentRepositoryPort) -> None:
        await students.add(a_student())

        with pytest.raises(DuplicateAggregateError):
            await students.add(a_student(matric="260591002"))

    async def test_saving_a_student_who_was_never_added_is_a_failure(
        self, students: StudentRepositoryPort
    ) -> None:
        with pytest.raises(AggregateNotFoundError):
            await students.save(a_student())

    async def test_a_correction_survives_a_save(self, students: StudentRepositoryPort) -> None:
        student = a_student()
        await students.add(student)

        student.correct_bio_data(BioData(full_name="Adaeze Okonkwo-Bello"))
        await students.save(student)

        stored = await students.get("stu-0001")
        assert stored is not None
        assert stored.bio_data.full_name == "Adaeze Okonkwo-Bello"

    async def test_a_student_is_found_by_the_number_they_quote(
        self, students: StudentRepositoryPort
    ) -> None:
        await students.add(a_student("stu-0001", "260591001"))
        wanted = a_student("stu-0002", "260591002")
        await students.add(wanted)

        assert await students.find_by_matric_number(MatricNumber("260591002")) is wanted

    async def test_an_unissued_matric_number_belongs_to_nobody(
        self, students: StudentRepositoryPort
    ) -> None:
        await students.add(a_student())

        assert await students.find_by_matric_number(MatricNumber("260591999")) is None

    async def test_a_matriculated_student_is_found_by_their_applicant_id(
        self, students: StudentRepositoryPort
    ) -> None:
        """This lookup is what makes a redelivered ``StudentMatriculated`` a no-op."""
        student = a_student(applicant_id="app-77")
        await students.add(student)

        assert await students.find_by_applicant("app-77") is student

    async def test_students_registered_by_hand_never_match_an_applicant_lookup(
        self, students: StudentRepositoryPort
    ) -> None:
        await students.add(a_student())

        assert await students.find_by_applicant("app-77") is None
        assert await students.find_by_applicant("") is None


class TestMatricSequenceRepository:
    async def test_the_first_ask_starts_the_counter(
        self, sequences: MatricSequenceRepositoryPort
    ) -> None:
        sequence = await sequences.get_or_start(CSC, YEAR_2026)

        assert sequence.issued == 0
        assert sequence.key == ("0591", 2026)

    async def test_asking_again_returns_the_same_counter(
        self, sequences: MatricSequenceRepositoryPort
    ) -> None:
        """Not a fresh one. A second counter for one intake is a duplicated number."""
        first = await sequences.get_or_start(CSC, YEAR_2026)
        first.take_next()

        assert (await sequences.get_or_start(CSC, YEAR_2026)).issued == 1

    async def test_each_department_and_year_gets_its_own_counter(
        self, sequences: MatricSequenceRepositoryPort
    ) -> None:
        (await sequences.get_or_start(CSC, YEAR_2026)).take_next()

        assert (await sequences.get_or_start(MCB, YEAR_2026)).issued == 0
        assert (await sequences.get_or_start(CSC, EntryYear(2027))).issued == 0

    async def test_an_intake_nobody_has_joined_is_not_an_error(
        self, sequences: MatricSequenceRepositoryPort
    ) -> None:
        assert await sequences.get(CSC, YEAR_2026) is None

    async def test_a_started_counter_can_be_read_back(
        self, sequences: MatricSequenceRepositoryPort
    ) -> None:
        (await sequences.get_or_start(CSC, YEAR_2026)).take_next()

        stored = await sequences.get(CSC, YEAR_2026)
        assert stored is not None
        assert stored.issued == 1

    async def test_saving_a_counter_that_was_never_started_is_a_failure(
        self, sequences: MatricSequenceRepositoryPort
    ) -> None:
        with pytest.raises(AggregateNotFoundError):
            await sequences.save(MatricSequence.start(CSC, YEAR_2026))

    async def test_concurrent_first_asks_share_one_counter(
        self, sequences: InMemoryMatricSequenceRepository
    ) -> None:
        """The race this adapter exists to absorb: two students being the first of an
        intake at the same instant must not produce two counters both at ordinal 1.

        Concurrent tasks rather than the thread pool this used before the repository ports
        became asynchronous. The assertions are the ones it always made. Against Postgres
        the test gets sharper rather than softer: ``get_or_start`` has real await points
        there, so these tasks interleave *inside* the operation, which is the interleaving
        the upsert and the row lock have to survive.
        """

        async def claim() -> int:
            return (await sequences.get_or_start(CSC, YEAR_2026)).take_next()

        claimed = await asyncio.gather(*(claim() for _ in range(200)))

        assert len(await sequences.all()) == 1
        assert sorted(claimed) == list(range(1, 201))
