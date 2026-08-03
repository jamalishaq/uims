"""The catalog's one repository port, against Postgres.

``Course`` reconstitutes through its own constructor: ``prerequisite_ids`` and ``active`` are
both ordinary arguments, so nothing here needs a ``restore``. What it does need is for the
prerequisites to arrive in the order they were added, which is what ``position`` is for.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import Row, Table
from sqlalchemy.ext.asyncio import AsyncEngine

from course_catalog.adapters.outbound.postgres import _tables as t
from course_catalog.adapters.outbound.postgres._repository import PostgresRepository
from course_catalog.domain.course import Course
from course_catalog.domain.values import require_code
from course_catalog.ports.course_repository import CourseRepositoryPort


class PostgresCourseRepository(PostgresRepository[Course], CourseRepositoryPort):
    """Holds the catalog in Postgres."""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(engine, label="course", table=t.courses, key=("course_id",))

    @property
    def child_tables(self) -> Sequence[tuple[Table, Sequence[str]]]:
        return ((t.course_prerequisites, ("course_id",)),)

    def identity_of(self, aggregate: Course) -> tuple[str]:
        return (aggregate.course_id,)

    def row_of(self, aggregate: Course) -> dict[str, Any]:
        return {
            "course_id": aggregate.course_id,
            "department_id": aggregate.department_id,
            "code": aggregate.code,
            "title": aggregate.title,
            "credit_units": aggregate.credit_units,
            "active": aggregate.is_active,
        }

    def child_rows_of(self, aggregate: Course) -> Mapping[Table, Sequence[dict[str, Any]]]:
        return {
            t.course_prerequisites: [
                {
                    "course_id": aggregate.course_id,
                    "prerequisite_id": prerequisite_id,
                    "position": position,
                }
                for position, prerequisite_id in enumerate(aggregate.prerequisite_ids)
            ]
        }

    def restore(self, row: Row[Any], children: Mapping[Table, Sequence[Row[Any]]]) -> Course:
        prerequisites = sorted(
            children.get(t.course_prerequisites, ()), key=lambda child: child.position
        )
        return Course(
            row.course_id,
            row.department_id,
            row.code,
            row.title,
            row.credit_units,
            prerequisite_ids=[child.prerequisite_id for child in prerequisites],
            active=row.active,
        )

    async def add(self, course: Course) -> None:
        await self._add(course)

    async def save(self, course: Course) -> None:
        await self._save(course)

    async def get(self, course_id: str) -> Course | None:
        return await self._get(course_id)

    async def list_all(self) -> tuple[Course, ...]:
        return await self._list()

    async def list_for_department(self, department_id: str) -> tuple[Course, ...]:
        return await self._list(t.courses.c.department_id == department_id)

    async def find_by_code(self, code: str) -> Course | None:
        """Normalises the argument the way ``Course`` normalises the stored code.

        The same line the in-memory adapter carries, and for the same reason: without it,
        ``find_by_code("csc101")`` would miss a stored ``CSC101`` and report a taken code as
        free. Normalising in Python rather than with ``upper()`` in SQL keeps the unique index
        on ``code`` usable, and keeps the definition of "the same code" in the one place the
        domain already put it.
        """
        return await self._find_one(t.courses.c.code == require_code(code, "course code"))
