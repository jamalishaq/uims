"""Student Profile's two repository ports, against Postgres.

``Student`` is ordinary: every field is a constructor argument, so it reconstitutes without a
``restore``. ``MatricSequence`` is not, and the difference is worth the reading — it is the
one repository in this system whose *concurrency* behaviour is part of the port's contract.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import Row, Table, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine

from persistence import resilient
from student_profile.adapters.outbound.postgres import _tables as t
from student_profile.adapters.outbound.postgres._errors import translating
from student_profile.adapters.outbound.postgres._repository import PostgresRepository
from student_profile.domain.matric_number import MatricNumber
from student_profile.domain.matric_sequence import MatricSequence
from student_profile.domain.student import Student
from student_profile.domain.values import BioData, DepartmentCode, EntryYear, Level
from student_profile.ports.matric_sequence_repository import MatricSequenceRepositoryPort
from student_profile.ports.student_repository import StudentRepositoryPort


class PostgresStudentRepository(PostgresRepository[Student], StudentRepositoryPort):
    """Holds students in Postgres. The two lookups become indexes rather than scans."""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(engine, label="student", table=t.students, key=("student_id",))

    def identity_of(self, aggregate: Student) -> tuple[str]:
        return (aggregate.student_id,)

    def row_of(self, aggregate: Student) -> dict[str, Any]:
        return {
            "student_id": aggregate.student_id,
            "matric_number": aggregate.matric_number.value,
            "full_name": aggregate.bio_data.full_name,
            "date_of_birth": aggregate.bio_data.date_of_birth,
            "email": aggregate.bio_data.email,
            "phone_number": aggregate.bio_data.phone_number,
            "program_id": aggregate.program_id,
            "entry_session_id": aggregate.entry_session_id,
            "entry_level": aggregate.entry_level.value,
            "applicant_id": aggregate.applicant_id,
        }

    def restore(self, row: Row[Any], children: Mapping[Table, Sequence[Row[Any]]]) -> Student:
        return Student(
            row.student_id,
            MatricNumber(row.matric_number),
            BioData(
                full_name=row.full_name,
                date_of_birth=row.date_of_birth,
                email=row.email,
                phone_number=row.phone_number,
            ),
            row.program_id,
            row.entry_session_id,
            Level(row.entry_level),
            applicant_id=row.applicant_id,
        )

    async def add(self, student: Student) -> None:
        await self._add(student)

    async def save(self, student: Student) -> None:
        await self._save(student)

    async def get(self, student_id: str) -> Student | None:
        return await self._get(student_id)

    async def find_by_matric_number(self, matric_number: MatricNumber) -> Student | None:
        """An index, where the in-memory adapter scanned — which is what its docstring said."""
        return await self._find_one(t.students.c.matric_number == matric_number.value)

    async def find_by_applicant(self, applicant_id: str) -> Student | None:
        """``None`` for a blank id, before any query is made.

        The in-memory adapter guards this too. Without it the empty string would go to the
        database as a value, and a NULL ``applicant_id`` would not match it — the right answer
        by luck rather than by intent, and one that would change the day somebody stored a
        student with an empty applicant id.
        """
        if not applicant_id:
            return None
        return await self._find_one(t.students.c.applicant_id == applicant_id)


class PostgresMatricSequenceRepository(
    PostgresRepository[MatricSequence], MatricSequenceRepositoryPort
):
    """Holds the per-department/year counters in Postgres.

    The port asks for something no other repository here is asked for: that ``get_or_start`` be
    **one atomic operation**, because "two callers racing on a department's first student of
    the year must receive *the same* sequence, or both will be handed ordinal 1 and two
    students will hold one matric number".

    Two mechanisms, and both are needed:

    * ``INSERT ... ON CONFLICT DO NOTHING`` then ``SELECT ... FOR UPDATE`` in one transaction.
      The upsert makes the row appear exactly once however many callers arrive together; the
      row lock serialises them behind it. This is what the port's docstring promised — "the
      in-memory adapter takes a lock, and Phase 6's Postgres adapter gets it from an upsert".
    * The identity map, so every caller in this process receives the *same*
      ``MatricSequence`` object and therefore the same in-process counter. Without it two
      hundred concurrent tasks would each be handed their own object reading ``issued = 0``,
      and every one of them would claim ordinal 1 — a duplicate number produced by a
      repository that was, row for row, perfectly correct.

    Between them they reproduce what the in-memory adapter got from a ``threading.Lock`` plus
    live references, which is exactly the pairing that adapter's docstring describes.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(
            engine,
            label="matric sequence",
            table=t.matric_sequences,
            key=("department_code", "entry_year"),
        )

    def identity_of(self, aggregate: MatricSequence) -> tuple[str, int]:
        return (aggregate.department_code.value, aggregate.entry_year.value)

    def row_of(self, aggregate: MatricSequence) -> dict[str, Any]:
        return {
            "department_code": aggregate.department_code.value,
            "entry_year": aggregate.entry_year.value,
            "issued": aggregate.issued,
        }

    def restore(
        self, row: Row[Any], children: Mapping[Table, Sequence[Row[Any]]]
    ) -> MatricSequence:
        return MatricSequence.restore(
            DepartmentCode(row.department_code), EntryYear(row.entry_year), row.issued
        )

    @resilient()
    async def get_or_start(
        self, department_code: DepartmentCode, entry_year: EntryYear
    ) -> MatricSequence:
        key = (department_code.value, entry_year.value)
        async with translating(self._describe(key)), self._engine.begin() as conn:
            await conn.execute(
                pg_insert(t.matric_sequences)
                .values(department_code=key[0], entry_year=key[1], issued=0)
                .on_conflict_do_nothing(index_elements=["department_code", "entry_year"])
            )
            row = (
                await conn.execute(
                    select(t.matric_sequences).where(self._key_match(key)).with_for_update()
                )
            ).one()
        return self._remember(key, self.restore(row, {}))

    async def save(self, sequence: MatricSequence) -> None:
        await self._save(sequence)

    async def get(
        self, department_code: DepartmentCode, entry_year: EntryYear
    ) -> MatricSequence | None:
        return await self._get(department_code.value, entry_year.value)

    async def all(self) -> tuple[MatricSequence, ...]:
        """Every counter started so far. Not on the port: for tests and reporting.

        The in-memory adapter carries the same method for the same reason, and the Student
        Profile conftest annotates its fixture concretely because of it.
        """
        return await self._list()
