"""Reference-data CRUD through the use cases.

Every test here goes through a port. Nothing names an adapter — the fixtures in
``conftest.py`` are the only place that does, so this file should still pass unchanged
against the Postgres adapters of Phase 6.
"""

import pytest

from course_catalog.application import (
    AmendCourse,
    AmendCourseCommand,
    CourseNotFoundError,
    DuplicateCourseCodeError,
    ListDepartmentCourses,
    ListDepartmentCoursesCommand,
    ReadCourse,
    ReadCourseCommand,
    RegisterCourse,
    RegisterCourseCommand,
    ReinstateCourse,
    ReinstateCourseCommand,
    RetireCourse,
    RetireCourseCommand,
)
from course_catalog.domain import InvalidCreditUnitsError, MissingIdentifierError
from course_catalog.ports import CourseRepositoryPort, DuplicateAggregateError

COURSE_ID = "crs-csc-101"
DEPARTMENT_ID = "dept-csc"


def a_command(**overrides: object) -> RegisterCourseCommand:
    fields: dict[str, object] = {
        "course_id": COURSE_ID,
        "department_id": DEPARTMENT_ID,
        "code": "CSC101",
        "title": "Introduction to Computer Science",
        "credit_units": 3,
    }
    fields.update(overrides)
    return RegisterCourseCommand(**fields)  # type: ignore[arg-type]


class TestRegisterCourse:
    async def test_a_registered_course_is_stored(
        self, register_course: RegisterCourse, courses: CourseRepositoryPort
    ) -> None:
        registered = await register_course.execute(a_command())

        assert await courses.get(COURSE_ID) is registered
        assert registered.code == "CSC101"

    async def test_a_registered_course_is_active_and_requires_nothing(
        self, register_course: RegisterCourse
    ) -> None:
        registered = await register_course.execute(a_command())

        assert registered.is_active is True
        assert registered.prerequisite_ids == ()

    async def test_a_second_course_cannot_take_a_code_already_in_use(
        self, register_course: RegisterCourse, courses: CourseRepositoryPort
    ) -> None:
        await register_course.execute(a_command())

        with pytest.raises(DuplicateCourseCodeError):
            await register_course.execute(a_command(course_id="crs-other", code="CSC101"))

        assert await courses.get("crs-other") is None

    async def test_the_code_clash_is_case_insensitive(
        self, register_course: RegisterCourse
    ) -> None:
        await register_course.execute(a_command())

        with pytest.raises(DuplicateCourseCodeError):
            await register_course.execute(a_command(course_id="crs-other", code="csc101"))

    async def test_a_second_course_cannot_take_an_id_already_in_use(
        self, register_course: RegisterCourse
    ) -> None:
        await register_course.execute(a_command())

        with pytest.raises(DuplicateAggregateError):
            await register_course.execute(a_command(code="CSC102"))

    async def test_domain_errors_reach_the_caller_untranslated(
        self, register_course: RegisterCourse
    ) -> None:
        """The domain already says exactly what went wrong."""
        with pytest.raises(InvalidCreditUnitsError):
            await register_course.execute(a_command(credit_units=0))

        with pytest.raises(MissingIdentifierError):
            await register_course.execute(a_command(title="   "))

    async def test_a_rejected_registration_stores_nothing(
        self, register_course: RegisterCourse, courses: CourseRepositoryPort
    ) -> None:
        with pytest.raises(InvalidCreditUnitsError):
            await register_course.execute(a_command(credit_units=-1))

        assert await courses.list_all() == ()


class TestReadCourse:
    async def test_a_stored_course_can_be_read_back(
        self, register_course: RegisterCourse, read_course: ReadCourse
    ) -> None:
        registered = await register_course.execute(a_command())

        assert await read_course.execute(ReadCourseCommand(COURSE_ID)) is registered

    async def test_an_unknown_id_is_an_error(self, read_course: ReadCourse) -> None:
        """Absence is an answer at the port, but a caller who names an id asserts it."""
        with pytest.raises(CourseNotFoundError):
            await read_course.execute(ReadCourseCommand("crs-nobody"))


class TestAmendCourse:
    async def test_a_title_can_be_corrected(
        self, register_course: RegisterCourse, amend_course: AmendCourse
    ) -> None:
        await register_course.execute(a_command())

        amended = await amend_course.execute(
            AmendCourseCommand(COURSE_ID, title="Intro to Computing")
        )

        assert amended.title == "Intro to Computing"

    async def test_omitted_fields_are_left_alone(
        self, register_course: RegisterCourse, amend_course: AmendCourse
    ) -> None:
        await register_course.execute(a_command())

        amended = await amend_course.execute(AmendCourseCommand(COURSE_ID, credit_units=4))

        assert amended.credit_units == 4
        assert amended.title == "Introduction to Computer Science"
        assert amended.department_id == DEPARTMENT_ID

    async def test_a_course_can_move_to_another_department(
        self, register_course: RegisterCourse, amend_course: AmendCourse
    ) -> None:
        await register_course.execute(a_command())

        amended = await amend_course.execute(
            AmendCourseCommand(COURSE_ID, department_id="dept-swe")
        )

        assert amended.department_id == "dept-swe"

    async def test_amending_an_unknown_course_is_an_error(self, amend_course: AmendCourse) -> None:
        with pytest.raises(CourseNotFoundError):
            await amend_course.execute(AmendCourseCommand("crs-nobody", title="Anything"))

    async def test_a_rejected_amendment_leaves_the_course_alone(
        self,
        register_course: RegisterCourse,
        amend_course: AmendCourse,
        read_course: ReadCourse,
    ) -> None:
        await register_course.execute(a_command())

        with pytest.raises(InvalidCreditUnitsError):
            await amend_course.execute(AmendCourseCommand(COURSE_ID, credit_units=0))

        assert (await read_course.execute(ReadCourseCommand(COURSE_ID))).credit_units == 3


class TestRetireAndReinstate:
    async def test_a_retired_course_is_no_longer_active(
        self, register_course: RegisterCourse, retire_course: RetireCourse
    ) -> None:
        await register_course.execute(a_command())

        assert (await retire_course.execute(RetireCourseCommand(COURSE_ID))).is_active is False

    async def test_a_retired_course_is_still_readable_by_id(
        self,
        register_course: RegisterCourse,
        retire_course: RetireCourse,
        read_course: ReadCourse,
    ) -> None:
        """Ids other contexts hold must keep resolving — that is why there is no delete."""
        await register_course.execute(a_command())
        await retire_course.execute(RetireCourseCommand(COURSE_ID))

        assert (await read_course.execute(ReadCourseCommand(COURSE_ID))).code == "CSC101"

    async def test_a_retired_course_can_be_reinstated(
        self,
        register_course: RegisterCourse,
        retire_course: RetireCourse,
        reinstate_course: ReinstateCourse,
    ) -> None:
        await register_course.execute(a_command())
        await retire_course.execute(RetireCourseCommand(COURSE_ID))

        assert (await reinstate_course.execute(ReinstateCourseCommand(COURSE_ID))).is_active is True

    async def test_a_retired_code_is_still_taken(
        self,
        register_course: RegisterCourse,
        retire_course: RetireCourse,
    ) -> None:
        """A withdrawn course still owns its code: transcripts elsewhere refer to it."""
        await register_course.execute(a_command())
        await retire_course.execute(RetireCourseCommand(COURSE_ID))

        with pytest.raises(DuplicateCourseCodeError):
            await register_course.execute(a_command(course_id="crs-other"))

    async def test_retiring_an_unknown_course_is_an_error(
        self, retire_course: RetireCourse
    ) -> None:
        with pytest.raises(CourseNotFoundError):
            await retire_course.execute(RetireCourseCommand("crs-nobody"))

    async def test_reinstating_an_unknown_course_is_an_error(
        self, reinstate_course: ReinstateCourse
    ) -> None:
        with pytest.raises(CourseNotFoundError):
            await reinstate_course.execute(ReinstateCourseCommand("crs-nobody"))


class TestListDepartmentCourses:
    async def test_only_the_named_department_is_listed(
        self, register_course: RegisterCourse, list_department_courses: ListDepartmentCourses
    ) -> None:
        computing = await register_course.execute(a_command())
        await register_course.execute(
            a_command(course_id="crs-phy-101", department_id="dept-phy", code="PHY101")
        )

        listed = await list_department_courses.execute(ListDepartmentCoursesCommand(DEPARTMENT_ID))

        assert listed == (computing,)

    async def test_courses_are_listed_in_the_order_they_were_added(
        self, register_course: RegisterCourse, list_department_courses: ListDepartmentCourses
    ) -> None:
        first = await register_course.execute(a_command())
        second = await register_course.execute(a_command(course_id="crs-csc-201", code="CSC201"))

        listed = await list_department_courses.execute(ListDepartmentCoursesCommand(DEPARTMENT_ID))

        assert listed == (first, second)

    async def test_retired_courses_are_left_out_by_default(
        self,
        register_course: RegisterCourse,
        retire_course: RetireCourse,
        list_department_courses: ListDepartmentCourses,
    ) -> None:
        active = await register_course.execute(a_command())
        await register_course.execute(a_command(course_id="crs-csc-999", code="CSC999"))
        await retire_course.execute(RetireCourseCommand("crs-csc-999"))

        listed = await list_department_courses.execute(ListDepartmentCoursesCommand(DEPARTMENT_ID))

        assert listed == (active,)

    async def test_the_administrative_view_can_ask_for_retired_courses(
        self,
        register_course: RegisterCourse,
        retire_course: RetireCourse,
        list_department_courses: ListDepartmentCourses,
    ) -> None:
        """Reinstating one means being able to see it first."""
        await register_course.execute(a_command())
        await register_course.execute(a_command(course_id="crs-csc-999", code="CSC999"))
        await retire_course.execute(RetireCourseCommand("crs-csc-999"))

        listed = await list_department_courses.execute(
            ListDepartmentCoursesCommand(DEPARTMENT_ID, include_retired=True)
        )

        assert [course.course_id for course in listed] == [COURSE_ID, "crs-csc-999"]

    async def test_a_department_offering_nothing_lists_nothing(
        self, list_department_courses: ListDepartmentCourses
    ) -> None:
        """This context cannot tell an empty department from an unknown one."""
        assert (
            await list_department_courses.execute(ListDepartmentCoursesCommand("dept-nobody")) == ()
        )
