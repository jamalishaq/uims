"""The contract the course repository adapter must keep.

This is the one file in the context's suite that names the adapter directly, because
it is the adapter that is under test. The Postgres adapter of Phase 6 has to pass this
same file — where the two would disagree is exactly the drift this catches.
"""

import pytest

from course_catalog.adapters.outbound import InMemoryCourseRepository
from course_catalog.domain import Course, MissingIdentifierError
from course_catalog.ports import AggregateNotFoundError, DuplicateAggregateError

DEPARTMENT_ID = "dept-csc"


def a_course(
    course_id: str = "crs-csc-101",
    department_id: str = DEPARTMENT_ID,
    code: str = "CSC101",
) -> Course:
    return Course.create(course_id, department_id, code, f"{code} Course", 3)


class TestStorageContract:
    async def test_an_added_course_comes_back(self) -> None:
        repository = InMemoryCourseRepository()
        course = a_course()

        await repository.add(course)

        assert await repository.get("crs-csc-101") is course

    async def test_an_unknown_id_returns_none(self) -> None:
        """Absence is an answer, not a failure."""
        assert await InMemoryCourseRepository().get("crs-nobody") is None

    async def test_adding_a_second_course_under_the_same_id_is_refused(self) -> None:
        repository = InMemoryCourseRepository()
        first = a_course()
        await repository.add(first)

        with pytest.raises(DuplicateAggregateError):
            await repository.add(a_course(code="CSC102"))

        assert await repository.get("crs-csc-101") is first

    async def test_save_replaces_a_stored_course(self) -> None:
        repository = InMemoryCourseRepository()
        await repository.add(a_course())
        replacement = a_course()

        await repository.save(replacement)

        assert await repository.get("crs-csc-101") is replacement

    async def test_save_on_an_id_that_was_never_added_is_refused(self) -> None:
        repository = InMemoryCourseRepository()

        with pytest.raises(AggregateNotFoundError):
            await repository.save(a_course())

        assert await repository.get("crs-csc-101") is None

    async def test_courses_are_kept_apart(self) -> None:
        repository = InMemoryCourseRepository()
        first = a_course("crs-csc-101", code="CSC101")
        second = a_course("crs-csc-201", code="CSC201")

        await repository.add(first)
        await repository.add(second)

        assert await repository.get("crs-csc-101") is first
        assert await repository.get("crs-csc-201") is second


class TestListAll:
    async def test_courses_are_listed_in_insertion_order(self) -> None:
        repository = InMemoryCourseRepository()
        later, earlier = a_course("crs-csc-301", code="CSC301"), a_course("crs-csc-101")
        await repository.add(later)
        await repository.add(earlier)

        assert await repository.list_all() == (later, earlier)

    async def test_an_empty_repository_lists_nothing(self) -> None:
        assert await InMemoryCourseRepository().list_all() == ()


class TestListForDepartment:
    async def test_courses_are_filtered_by_department(self) -> None:
        repository = InMemoryCourseRepository()
        computing = a_course("crs-csc-101", "dept-csc", "CSC101")
        await repository.add(computing)
        await repository.add(a_course("crs-phy-101", "dept-phy", "PHY101"))

        assert await repository.list_for_department("dept-csc") == (computing,)

    async def test_a_department_offering_nothing_lists_nothing(self) -> None:
        repository = InMemoryCourseRepository()
        await repository.add(a_course())

        assert await repository.list_for_department("dept-nobody") == ()

    async def test_retired_courses_are_still_listed(self) -> None:
        """Filtering by status is the use case's job; the port reports what it holds."""
        repository = InMemoryCourseRepository()
        course = a_course()
        course.retire()
        await repository.add(course)

        assert await repository.list_for_department(DEPARTMENT_ID) == (course,)


class TestFindByCode:
    async def test_a_stored_code_is_found(self) -> None:
        repository = InMemoryCourseRepository()
        course = a_course()
        await repository.add(course)

        assert await repository.find_by_code("CSC101") is course

    async def test_lookup_is_case_insensitive_because_storage_is(self) -> None:
        """Otherwise a taken code would come back free, and the clash check would pass."""
        repository = InMemoryCourseRepository()
        course = a_course()
        await repository.add(course)

        assert await repository.find_by_code("csc101") is course
        assert await repository.find_by_code("  csc101  ") is course

    async def test_an_unused_code_returns_none(self) -> None:
        repository = InMemoryCourseRepository()
        await repository.add(a_course())

        assert await repository.find_by_code("PHY101") is None

    async def test_a_blank_code_is_refused(self) -> None:
        with pytest.raises(MissingIdentifierError):
            await InMemoryCourseRepository().find_by_code("   ")


class TestPrerequisitesTravelWithTheCourse:
    async def test_a_stored_course_keeps_the_prerequisites_it_was_given(self) -> None:
        """Prerequisites are part of the aggregate, so the repository must carry them."""
        repository = InMemoryCourseRepository()
        course = a_course("crs-csc-201", code="CSC201")
        course.add_prerequisite("crs-csc-101")
        await repository.add(course)

        stored = await repository.get("crs-csc-201")

        assert stored is not None
        assert stored.requires("crs-csc-101")
