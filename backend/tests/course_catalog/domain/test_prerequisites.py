"""Reading prerequisite chains, and refusing to create circular ones.

The graph is constructed with a plain dict lookup rather than a repository. That is the
point of taking a callable: this file exercises the whole rule with no adapter in
sight, which is what "domain tests use zero infrastructure" means.

The lookup is a coroutine because the graph awaits it — the one place in any ``domain/``
package that does, and the module's own docstring says why. A dict is still the whole of
the infrastructure here: ``looking_up`` adds no storage, only the ``await`` that a real
repository would make necessary.
"""

import pytest

from course_catalog.domain import (
    Course,
    PrerequisiteCycleError,
    PrerequisiteGraph,
    SelfPrerequisiteError,
)

DEPARTMENT_ID = "dept-csc"


def a_course(course_id: str, code: str, *prerequisite_ids: str) -> Course:
    return Course(
        course_id,
        DEPARTMENT_ID,
        code,
        f"{code} Course",
        3,
        prerequisite_ids=prerequisite_ids,
    )


def a_graph(*courses: Course) -> PrerequisiteGraph:
    catalog = {course.course_id: course for course in courses}

    async def looking_up(course_id: str) -> Course | None:
        return catalog.get(course_id)

    return PrerequisiteGraph(looking_up)


class TestReadingAChain:
    async def test_a_course_with_no_prerequisites_has_an_empty_chain(self) -> None:
        intro = a_course("crs-csc-101", "CSC101")

        assert await a_graph(intro).chain_for("crs-csc-101") == ()

    async def test_a_direct_prerequisite_is_reported(self) -> None:
        intro = a_course("crs-csc-101", "CSC101")
        data_structures = a_course("crs-csc-201", "CSC201", "crs-csc-101")

        chain = await a_graph(intro, data_structures).chain_for("crs-csc-201")

        assert chain == ("crs-csc-101",)

    async def test_a_chain_is_followed_all_the_way_down(self) -> None:
        """The verification criterion: prerequisite chains can be read."""
        intro = a_course("crs-csc-101", "CSC101")
        data_structures = a_course("crs-csc-201", "CSC201", "crs-csc-101")
        algorithms = a_course("crs-csc-301", "CSC301", "crs-csc-201")

        chain = await a_graph(intro, data_structures, algorithms).chain_for("crs-csc-301")

        assert chain == ("crs-csc-201", "crs-csc-101")

    async def test_nearer_prerequisites_come_first(self) -> None:
        intro = a_course("crs-csc-101", "CSC101")
        maths = a_course("crs-mth-101", "MTH101")
        data_structures = a_course("crs-csc-201", "CSC201", "crs-csc-101")
        algorithms = a_course("crs-csc-301", "CSC301", "crs-csc-201", "crs-mth-101")

        chain = await a_graph(intro, maths, data_structures, algorithms).chain_for("crs-csc-301")

        assert chain == ("crs-csc-201", "crs-mth-101", "crs-csc-101")

    async def test_a_diamond_reports_each_course_once(self) -> None:
        """Two second-year courses both resting on CSC101 do not report it twice."""
        intro = a_course("crs-csc-101", "CSC101")
        data_structures = a_course("crs-csc-201", "CSC201", "crs-csc-101")
        systems = a_course("crs-csc-202", "CSC202", "crs-csc-101")
        project = a_course("crs-csc-401", "CSC401", "crs-csc-201", "crs-csc-202")

        chain = await a_graph(intro, data_structures, systems, project).chain_for("crs-csc-401")

        assert chain == ("crs-csc-201", "crs-csc-202", "crs-csc-101")

    async def test_the_course_itself_is_never_in_its_own_chain(self) -> None:
        intro = a_course("crs-csc-101", "CSC101")
        data_structures = a_course("crs-csc-201", "CSC201", "crs-csc-101")

        assert "crs-csc-201" not in await a_graph(intro, data_structures).chain_for("crs-csc-201")

    async def test_an_unresolvable_prerequisite_id_contributes_nothing(self) -> None:
        """Whether a stored id ought to resolve is the application layer's question."""
        data_structures = a_course("crs-csc-201", "CSC201", "crs-csc-101")

        assert await a_graph(data_structures).chain_for("crs-csc-201") == ("crs-csc-101",)

    async def test_an_unknown_course_has_an_empty_chain(self) -> None:
        assert await a_graph().chain_for("crs-nobody") == ()


class TestChainsOverCyclicData:
    """``AddPrerequisite`` refuses to create these, but a reader that could hang on bad
    data is a reader that will hang on bad data."""

    async def test_a_two_course_loop_terminates(self) -> None:
        first = a_course("crs-csc-101", "CSC101", "crs-csc-201")
        second = a_course("crs-csc-201", "CSC201", "crs-csc-101")

        assert await a_graph(first, second).chain_for("crs-csc-101") == ("crs-csc-201",)

    async def test_a_longer_loop_terminates(self) -> None:
        first = a_course("crs-csc-101", "CSC101", "crs-csc-301")
        second = a_course("crs-csc-201", "CSC201", "crs-csc-101")
        third = a_course("crs-csc-301", "CSC301", "crs-csc-201")

        chain = await a_graph(first, second, third).chain_for("crs-csc-101")

        assert chain == ("crs-csc-301", "crs-csc-201")


class TestRefusingACycle:
    async def test_an_unrelated_prerequisite_is_allowed(self) -> None:
        intro = a_course("crs-csc-101", "CSC101")
        data_structures = a_course("crs-csc-201", "CSC201")

        await a_graph(intro, data_structures).ensure_can_require(data_structures, "crs-csc-101")

    async def test_requiring_a_course_that_already_requires_you_is_refused(self) -> None:
        intro = a_course("crs-csc-101", "CSC101")
        data_structures = a_course("crs-csc-201", "CSC201", "crs-csc-101")

        with pytest.raises(PrerequisiteCycleError):
            await a_graph(intro, data_structures).ensure_can_require(intro, "crs-csc-201")

    async def test_a_cycle_further_down_the_chain_is_refused(self) -> None:
        """CSC301 → CSC201 → CSC101, so CSC101 may not require CSC301."""
        intro = a_course("crs-csc-101", "CSC101")
        data_structures = a_course("crs-csc-201", "CSC201", "crs-csc-101")
        algorithms = a_course("crs-csc-301", "CSC301", "crs-csc-201")

        with pytest.raises(PrerequisiteCycleError):
            await a_graph(intro, data_structures, algorithms).ensure_can_require(
                intro, "crs-csc-301"
            )

    async def test_direct_self_reference_is_left_to_the_entity(self) -> None:
        """The graph stays silent so ``Course`` can say it more precisely."""
        intro = a_course("crs-csc-101", "CSC101")

        await a_graph(intro).ensure_can_require(intro, "crs-csc-101")

        with pytest.raises(SelfPrerequisiteError):
            intro.add_prerequisite("crs-csc-101")
