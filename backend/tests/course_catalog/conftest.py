"""Wiring for the Course Catalog tests.

This module is the swap point, and Phase 6.1 is what it was waiting for. ``courses`` now
comes from ``adapters``, which resolves to the in-memory class or the Postgres one depending
on ``UMS_TEST_BACKEND`` — see ``tests/conftest.py``. Adapter construction still happens *only*
here, and every fixture is still annotated with its port type rather than the concrete class.
A test that names an adapter directly is a test that would have to be rewritten later; not one
in this context did, which is why not one of them changed.
"""

import pytest
from tests.conftest import Adapters

from course_catalog.application import (
    AddPrerequisite,
    AmendCourse,
    ListDepartmentCourses,
    ReadCourse,
    ReadPrerequisiteChain,
    RegisterCourse,
    ReinstateCourse,
    RemovePrerequisite,
    RetireCourse,
)
from course_catalog.ports import CourseRepositoryPort


@pytest.fixture
def courses(adapters: Adapters) -> CourseRepositoryPort:
    return adapters.courses()


@pytest.fixture
def register_course(courses: CourseRepositoryPort) -> RegisterCourse:
    return RegisterCourse(courses)


@pytest.fixture
def amend_course(courses: CourseRepositoryPort) -> AmendCourse:
    return AmendCourse(courses)


@pytest.fixture
def read_course(courses: CourseRepositoryPort) -> ReadCourse:
    return ReadCourse(courses)


@pytest.fixture
def list_department_courses(courses: CourseRepositoryPort) -> ListDepartmentCourses:
    return ListDepartmentCourses(courses)


@pytest.fixture
def retire_course(courses: CourseRepositoryPort) -> RetireCourse:
    return RetireCourse(courses)


@pytest.fixture
def reinstate_course(courses: CourseRepositoryPort) -> ReinstateCourse:
    return ReinstateCourse(courses)


@pytest.fixture
def add_prerequisite(courses: CourseRepositoryPort) -> AddPrerequisite:
    return AddPrerequisite(courses)


@pytest.fixture
def remove_prerequisite(courses: CourseRepositoryPort) -> RemovePrerequisite:
    return RemovePrerequisite(courses)


@pytest.fixture
def read_prerequisite_chain(courses: CourseRepositoryPort) -> ReadPrerequisiteChain:
    return ReadPrerequisiteChain(courses)
