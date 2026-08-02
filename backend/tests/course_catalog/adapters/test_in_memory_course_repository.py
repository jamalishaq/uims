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
    def test_an_added_course_comes_back(self) -> None:
        repository = InMemoryCourseRepository()
        course = a_course()

        repository.add(course)

        assert repository.get("crs-csc-101") is course

    def test_an_unknown_id_returns_none(self) -> None:
        """Absence is an answer, not a failure."""
        assert InMemoryCourseRepository().get("crs-nobody") is None

    def test_adding_a_second_course_under_the_same_id_is_refused(self) -> None:
        repository = InMemoryCourseRepository()
        first = a_course()
        repository.add(first)

        with pytest.raises(DuplicateAggregateError):
            repository.add(a_course(code="CSC102"))

        assert repository.get("crs-csc-101") is first

    def test_save_replaces_a_stored_course(self) -> None:
        repository = InMemoryCourseRepository()
        repository.add(a_course())
        replacement = a_course()

        repository.save(replacement)

        assert repository.get("crs-csc-101") is replacement

    def test_save_on_an_id_that_was_never_added_is_refused(self) -> None:
        repository = InMemoryCourseRepository()

        with pytest.raises(AggregateNotFoundError):
            repository.save(a_course())

        assert repository.get("crs-csc-101") is None

    def test_courses_are_kept_apart(self) -> None:
        repository = InMemoryCourseRepository()
        first = a_course("crs-csc-101", code="CSC101")
        second = a_course("crs-csc-201", code="CSC201")

        repository.add(first)
        repository.add(second)

        assert repository.get("crs-csc-101") is first
        assert repository.get("crs-csc-201") is second


class TestListAll:
    def test_courses_are_listed_in_insertion_order(self) -> None:
        repository = InMemoryCourseRepository()
        later, earlier = a_course("crs-csc-301", code="CSC301"), a_course("crs-csc-101")
        repository.add(later)
        repository.add(earlier)

        assert repository.list_all() == (later, earlier)

    def test_an_empty_repository_lists_nothing(self) -> None:
        assert InMemoryCourseRepository().list_all() == ()


class TestListForDepartment:
    def test_courses_are_filtered_by_department(self) -> None:
        repository = InMemoryCourseRepository()
        computing = a_course("crs-csc-101", "dept-csc", "CSC101")
        repository.add(computing)
        repository.add(a_course("crs-phy-101", "dept-phy", "PHY101"))

        assert repository.list_for_department("dept-csc") == (computing,)

    def test_a_department_offering_nothing_lists_nothing(self) -> None:
        repository = InMemoryCourseRepository()
        repository.add(a_course())

        assert repository.list_for_department("dept-nobody") == ()

    def test_retired_courses_are_still_listed(self) -> None:
        """Filtering by status is the use case's job; the port reports what it holds."""
        repository = InMemoryCourseRepository()
        course = a_course()
        course.retire()
        repository.add(course)

        assert repository.list_for_department(DEPARTMENT_ID) == (course,)


class TestFindByCode:
    def test_a_stored_code_is_found(self) -> None:
        repository = InMemoryCourseRepository()
        course = a_course()
        repository.add(course)

        assert repository.find_by_code("CSC101") is course

    def test_lookup_is_case_insensitive_because_storage_is(self) -> None:
        """Otherwise a taken code would come back free, and the clash check would pass."""
        repository = InMemoryCourseRepository()
        course = a_course()
        repository.add(course)

        assert repository.find_by_code("csc101") is course
        assert repository.find_by_code("  csc101  ") is course

    def test_an_unused_code_returns_none(self) -> None:
        repository = InMemoryCourseRepository()
        repository.add(a_course())

        assert repository.find_by_code("PHY101") is None

    def test_a_blank_code_is_refused(self) -> None:
        with pytest.raises(MissingIdentifierError):
            InMemoryCourseRepository().find_by_code("   ")


class TestPrerequisitesTravelWithTheCourse:
    def test_a_stored_course_keeps_the_prerequisites_it_was_given(self) -> None:
        """Prerequisites are part of the aggregate, so the repository must carry them."""
        repository = InMemoryCourseRepository()
        course = a_course("crs-csc-201", code="CSC201")
        course.add_prerequisite("crs-csc-101")
        repository.add(course)

        stored = repository.get("crs-csc-201")

        assert stored is not None
        assert stored.requires("crs-csc-101")
