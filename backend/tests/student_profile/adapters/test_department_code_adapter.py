"""The anti-corruption adapter in front of Faculty & Department.

What is being checked is mostly the boundary itself: that the answers come back in this
context's types, that a question about something that context has never heard of is
answered rather than raised, and that an invalid mapping fails when it is registered
rather than at the moment a student is waiting for a number.
"""

import pytest

from student_profile.adapters.outbound import InMemoryDepartmentCodeAdapter
from student_profile.domain import (
    DepartmentCode,
    EntryYear,
    InvalidDepartmentCodeError,
    InvalidEntryYearError,
)
from student_profile.ports import MatricFormatInputs

PROGRAM_ID = "prog-csc-bsc"
SESSION_ID = "sess-2026"


@pytest.fixture
def adapter() -> InMemoryDepartmentCodeAdapter:
    return InMemoryDepartmentCodeAdapter()


class TestAnswering:
    async def test_it_answers_in_this_context_s_own_types(
        self, adapter: InMemoryDepartmentCodeAdapter
    ) -> None:
        """Nothing of Faculty & Department's crosses the port — that is the whole job."""
        adapter.register(PROGRAM_ID, SESSION_ID, "0591", 2026)

        assert await adapter.format_inputs_for(PROGRAM_ID, SESSION_ID) == MatricFormatInputs(
            department_code=DepartmentCode("0591"), entry_year=EntryYear(2026)
        )

    async def test_an_unknown_program_is_answered_with_nothing(
        self, adapter: InMemoryDepartmentCodeAdapter
    ) -> None:
        """A question with a correct negative reply, not a failure. What to do about it
        is the application layer's judgment."""
        assert await adapter.format_inputs_for("prog-nobody", SESSION_ID) is None

    async def test_a_program_in_a_session_it_has_no_placement_for_is_answered_with_nothing(
        self, adapter: InMemoryDepartmentCodeAdapter
    ) -> None:
        adapter.register(PROGRAM_ID, SESSION_ID, "0591", 2026)

        assert await adapter.format_inputs_for(PROGRAM_ID, "sess-2030") is None

    async def test_one_program_can_run_across_sessions(
        self, adapter: InMemoryDepartmentCodeAdapter
    ) -> None:
        adapter.register(PROGRAM_ID, SESSION_ID, "0591", 2026)
        adapter.register(PROGRAM_ID, "sess-2027", "0591", 2027)

        assert await adapter.format_inputs_for(PROGRAM_ID, "sess-2027") == MatricFormatInputs(
            department_code=DepartmentCode("0591"), entry_year=EntryYear(2027)
        )

    async def test_two_programs_can_share_a_department(
        self, adapter: InMemoryDepartmentCodeAdapter
    ) -> None:
        """Software Engineering and Computer Science both sit under one department, and
        their students share one intake counter as a result."""
        adapter.register(PROGRAM_ID, SESSION_ID, "0591", 2026)
        adapter.register("prog-swe-bsc", SESSION_ID, "0591", 2026)

        first = await adapter.format_inputs_for(PROGRAM_ID, SESSION_ID)
        second = await adapter.format_inputs_for("prog-swe-bsc", SESSION_ID)
        assert first == second

    async def test_a_later_registration_replaces_an_earlier_one(
        self, adapter: InMemoryDepartmentCodeAdapter
    ) -> None:
        adapter.register(PROGRAM_ID, SESSION_ID, "0591", 2026)
        adapter.register(PROGRAM_ID, SESSION_ID, "0672", 2026)

        inputs = await adapter.format_inputs_for(PROGRAM_ID, SESSION_ID)
        assert inputs is not None
        assert inputs.department_code == DepartmentCode("0672")


class TestTranslationFailsAtTheBoundary:
    """A bad mapping is caught when it is registered, not when a student is waiting."""

    @pytest.mark.parametrize("code", ["CSC", "591", "05910", ""])
    def test_a_code_that_is_not_the_numeric_form_is_rejected(
        self, adapter: InMemoryDepartmentCodeAdapter, code: str
    ) -> None:
        with pytest.raises(InvalidDepartmentCodeError):
            adapter.register(PROGRAM_ID, SESSION_ID, code, 2026)

    @pytest.mark.parametrize("year", [26, 1899, 3000])
    def test_an_implausible_year_is_rejected(
        self, adapter: InMemoryDepartmentCodeAdapter, year: int
    ) -> None:
        """``26`` in particular: the two-digit form belongs to the rendering, not here."""
        with pytest.raises(InvalidEntryYearError):
            adapter.register(PROGRAM_ID, SESSION_ID, "0591", year)

    async def test_a_rejected_registration_leaves_no_placement_behind(
        self, adapter: InMemoryDepartmentCodeAdapter
    ) -> None:
        with pytest.raises(InvalidDepartmentCodeError):
            adapter.register(PROGRAM_ID, SESSION_ID, "CSC", 2026)

        assert await adapter.format_inputs_for(PROGRAM_ID, SESSION_ID) is None
