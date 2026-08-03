"""Wiring courses into a curriculum, and reading the result back.

The two acceptance criteria for this context live here in their end-to-end form: a
chain can be read through the use case, and no sequence of calls through the use case
can make a course require itself.
"""

import pytest

from course_catalog.application import (
    AddPrerequisite,
    AddPrerequisiteCommand,
    CourseNotFoundError,
    PrerequisiteCourseNotFoundError,
    ReadPrerequisiteChain,
    ReadPrerequisiteChainCommand,
    RegisterCourse,
    RegisterCourseCommand,
    RemovePrerequisite,
    RemovePrerequisiteCommand,
    RetireCourse,
    RetireCourseCommand,
)
from course_catalog.domain import (
    DuplicatePrerequisiteError,
    PrerequisiteCycleError,
    PrerequisiteNotRequiredError,
    SelfPrerequisiteError,
)
from course_catalog.ports import CourseRepositoryPort

DEPARTMENT_ID = "dept-csc"

INTRO = "crs-csc-101"
DATA_STRUCTURES = "crs-csc-201"
ALGORITHMS = "crs-csc-301"
MATHS = "crs-mth-101"

CODES = {
    INTRO: "CSC101",
    DATA_STRUCTURES: "CSC201",
    ALGORITHMS: "CSC301",
    MATHS: "MTH101",
}


@pytest.fixture
async def catalog(register_course: RegisterCourse) -> RegisterCourse:
    """Four registered courses, none of them requiring anything yet."""
    for course_id, code in CODES.items():
        await register_course.execute(
            RegisterCourseCommand(course_id, DEPARTMENT_ID, code, f"{code} Course", 3)
        )
    return register_course


@pytest.mark.usefixtures("catalog")
class TestAddPrerequisite:
    async def test_a_prerequisite_is_recorded(
        self, add_prerequisite: AddPrerequisite, courses: CourseRepositoryPort
    ) -> None:
        await add_prerequisite.execute(AddPrerequisiteCommand(DATA_STRUCTURES, INTRO))

        stored = await courses.get(DATA_STRUCTURES)
        assert stored is not None
        assert stored.requires(INTRO)

    async def test_a_course_cannot_require_itself(self, add_prerequisite: AddPrerequisite) -> None:
        """The verification criterion, reached through the use case.

        The domain error arrives untranslated: nothing in the application layer
        restates the rule, and nothing rewraps the sentence the domain used to say it.
        """
        with pytest.raises(SelfPrerequisiteError):
            await add_prerequisite.execute(AddPrerequisiteCommand(INTRO, INTRO))

    async def test_a_two_course_loop_is_refused(self, add_prerequisite: AddPrerequisite) -> None:
        await add_prerequisite.execute(AddPrerequisiteCommand(DATA_STRUCTURES, INTRO))

        with pytest.raises(PrerequisiteCycleError):
            await add_prerequisite.execute(AddPrerequisiteCommand(INTRO, DATA_STRUCTURES))

    async def test_a_longer_loop_is_refused(self, add_prerequisite: AddPrerequisite) -> None:
        """CSC301 → CSC201 → CSC101, so CSC101 may not require CSC301."""
        await add_prerequisite.execute(AddPrerequisiteCommand(DATA_STRUCTURES, INTRO))
        await add_prerequisite.execute(AddPrerequisiteCommand(ALGORITHMS, DATA_STRUCTURES))

        with pytest.raises(PrerequisiteCycleError):
            await add_prerequisite.execute(AddPrerequisiteCommand(INTRO, ALGORITHMS))

    async def test_a_refused_cycle_changes_nothing(
        self, add_prerequisite: AddPrerequisite, courses: CourseRepositoryPort
    ) -> None:
        """The check runs before the aggregate is touched: nothing to unwind."""
        await add_prerequisite.execute(AddPrerequisiteCommand(DATA_STRUCTURES, INTRO))

        with pytest.raises(PrerequisiteCycleError):
            await add_prerequisite.execute(AddPrerequisiteCommand(INTRO, DATA_STRUCTURES))

        stored = await courses.get(INTRO)
        assert stored is not None
        assert stored.prerequisite_ids == ()

    async def test_a_shared_prerequisite_is_not_a_cycle(
        self, add_prerequisite: AddPrerequisite, courses: CourseRepositoryPort
    ) -> None:
        """A diamond is a normal curriculum, not a loop."""
        await add_prerequisite.execute(AddPrerequisiteCommand(DATA_STRUCTURES, INTRO))
        await add_prerequisite.execute(AddPrerequisiteCommand(ALGORITHMS, INTRO))

        stored = await courses.get(ALGORITHMS)
        assert stored is not None
        assert stored.requires(INTRO)

    async def test_the_same_prerequisite_cannot_be_added_twice(
        self, add_prerequisite: AddPrerequisite
    ) -> None:
        await add_prerequisite.execute(AddPrerequisiteCommand(DATA_STRUCTURES, INTRO))

        with pytest.raises(DuplicatePrerequisiteError):
            await add_prerequisite.execute(AddPrerequisiteCommand(DATA_STRUCTURES, INTRO))

    async def test_an_unknown_course_is_a_lookup_miss(
        self, add_prerequisite: AddPrerequisite
    ) -> None:
        with pytest.raises(CourseNotFoundError):
            await add_prerequisite.execute(AddPrerequisiteCommand("crs-nobody", INTRO))

    async def test_an_unknown_prerequisite_is_refused(
        self, add_prerequisite: AddPrerequisite
    ) -> None:
        """A prerequisite id is ours to vouch for, unlike a department id."""
        with pytest.raises(PrerequisiteCourseNotFoundError):
            await add_prerequisite.execute(AddPrerequisiteCommand(DATA_STRUCTURES, "crs-nobody"))

    async def test_a_retired_course_may_still_be_named_as_a_prerequisite(
        self, add_prerequisite: AddPrerequisite, retire_course: RetireCourse
    ) -> None:
        """Retired means "no longer offered", not "never happened"."""
        await retire_course.execute(RetireCourseCommand(INTRO))

        amended = await add_prerequisite.execute(AddPrerequisiteCommand(DATA_STRUCTURES, INTRO))

        assert amended.requires(INTRO)


@pytest.mark.usefixtures("catalog")
class TestRemovePrerequisite:
    async def test_a_prerequisite_can_be_dropped(
        self,
        add_prerequisite: AddPrerequisite,
        remove_prerequisite: RemovePrerequisite,
        courses: CourseRepositoryPort,
    ) -> None:
        await add_prerequisite.execute(AddPrerequisiteCommand(DATA_STRUCTURES, INTRO))

        await remove_prerequisite.execute(RemovePrerequisiteCommand(DATA_STRUCTURES, INTRO))

        stored = await courses.get(DATA_STRUCTURES)
        assert stored is not None
        assert stored.prerequisite_ids == ()

    async def test_dropping_one_a_course_never_had_is_refused(
        self, remove_prerequisite: RemovePrerequisite
    ) -> None:
        with pytest.raises(PrerequisiteNotRequiredError):
            await remove_prerequisite.execute(RemovePrerequisiteCommand(DATA_STRUCTURES, INTRO))

    async def test_dropping_from_an_unknown_course_is_a_lookup_miss(
        self, remove_prerequisite: RemovePrerequisite
    ) -> None:
        with pytest.raises(CourseNotFoundError):
            await remove_prerequisite.execute(RemovePrerequisiteCommand("crs-nobody", INTRO))


@pytest.mark.usefixtures("catalog")
class TestReadPrerequisiteChain:
    async def test_a_course_with_no_prerequisites_has_an_empty_chain(
        self, read_prerequisite_chain: ReadPrerequisiteChain
    ) -> None:
        assert await read_prerequisite_chain.execute(ReadPrerequisiteChainCommand(INTRO)) == ()

    async def test_a_chain_is_followed_all_the_way_down(
        self, add_prerequisite: AddPrerequisite, read_prerequisite_chain: ReadPrerequisiteChain
    ) -> None:
        """The verification criterion: prerequisite chains can be read."""
        await add_prerequisite.execute(AddPrerequisiteCommand(DATA_STRUCTURES, INTRO))
        await add_prerequisite.execute(AddPrerequisiteCommand(ALGORITHMS, DATA_STRUCTURES))

        chain = await read_prerequisite_chain.execute(ReadPrerequisiteChainCommand(ALGORITHMS))

        assert chain == (DATA_STRUCTURES, INTRO)

    async def test_nearer_prerequisites_come_first(
        self, add_prerequisite: AddPrerequisite, read_prerequisite_chain: ReadPrerequisiteChain
    ) -> None:
        await add_prerequisite.execute(AddPrerequisiteCommand(DATA_STRUCTURES, INTRO))
        await add_prerequisite.execute(AddPrerequisiteCommand(ALGORITHMS, DATA_STRUCTURES))
        await add_prerequisite.execute(AddPrerequisiteCommand(ALGORITHMS, MATHS))

        chain = await read_prerequisite_chain.execute(ReadPrerequisiteChainCommand(ALGORITHMS))

        assert chain == (DATA_STRUCTURES, MATHS, INTRO)

    async def test_a_diamond_reports_each_course_once(
        self, add_prerequisite: AddPrerequisite, read_prerequisite_chain: ReadPrerequisiteChain
    ) -> None:
        await add_prerequisite.execute(AddPrerequisiteCommand(DATA_STRUCTURES, INTRO))
        await add_prerequisite.execute(AddPrerequisiteCommand(MATHS, INTRO))
        await add_prerequisite.execute(AddPrerequisiteCommand(ALGORITHMS, DATA_STRUCTURES))
        await add_prerequisite.execute(AddPrerequisiteCommand(ALGORITHMS, MATHS))

        chain = await read_prerequisite_chain.execute(ReadPrerequisiteChainCommand(ALGORITHMS))

        assert chain == (DATA_STRUCTURES, MATHS, INTRO)

    async def test_dropping_a_prerequisite_shortens_the_chain(
        self,
        add_prerequisite: AddPrerequisite,
        remove_prerequisite: RemovePrerequisite,
        read_prerequisite_chain: ReadPrerequisiteChain,
    ) -> None:
        await add_prerequisite.execute(AddPrerequisiteCommand(DATA_STRUCTURES, INTRO))
        await add_prerequisite.execute(AddPrerequisiteCommand(ALGORITHMS, DATA_STRUCTURES))

        await remove_prerequisite.execute(RemovePrerequisiteCommand(DATA_STRUCTURES, INTRO))

        chain = await read_prerequisite_chain.execute(ReadPrerequisiteChainCommand(ALGORITHMS))

        assert chain == (DATA_STRUCTURES,)

    async def test_reading_the_chain_of_an_unknown_course_is_an_error(
        self, read_prerequisite_chain: ReadPrerequisiteChain
    ) -> None:
        with pytest.raises(CourseNotFoundError):
            await read_prerequisite_chain.execute(ReadPrerequisiteChainCommand("crs-nobody"))
