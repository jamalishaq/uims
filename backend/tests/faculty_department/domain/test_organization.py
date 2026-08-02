"""Faculty, Department and Program: construction invariants and admissions state.

Three separate aggregates referencing each other by id, never one nested tree.
"""

import pytest

from faculty_department.domain import Department, Faculty, MissingIdentifierError, Program


class TestFaculty:
    def test_carries_its_identity_name_and_code(self) -> None:
        faculty = Faculty("fac-sci", "Faculty of Science", "SCI")
        assert (faculty.faculty_id, faculty.name, faculty.code) == (
            "fac-sci",
            "Faculty of Science",
            "SCI",
        )

    def test_code_is_normalised_to_upper_case(self) -> None:
        assert Faculty("fac-sci", "Faculty of Science", " sci ").code == "SCI"

    def test_can_be_renamed(self) -> None:
        faculty = Faculty("fac-sci", "Faculty of Science", "SCI")
        faculty.rename("Faculty of Natural Sciences")
        assert faculty.name == "Faculty of Natural Sciences"

    @pytest.mark.parametrize(
        ("faculty_id", "name", "code"),
        [
            ("", "Faculty of Science", "SCI"),
            ("   ", "Faculty of Science", "SCI"),
            ("fac-sci", "", "SCI"),
            ("fac-sci", "Faculty of Science", "  "),
        ],
    )
    def test_cannot_be_built_with_a_blank_field(
        self, faculty_id: str, name: str, code: str
    ) -> None:
        with pytest.raises(MissingIdentifierError):
            Faculty(faculty_id, name, code)

    def test_renaming_to_blank_is_rejected(self) -> None:
        faculty = Faculty("fac-sci", "Faculty of Science", "SCI")
        with pytest.raises(MissingIdentifierError):
            faculty.rename("   ")
        assert faculty.name == "Faculty of Science"


class TestDepartment:
    def test_references_its_faculty_by_id(self) -> None:
        department = Department("dept-csc", "fac-sci", "Computer Science", "CSC")
        assert department.faculty_id == "fac-sci"
        assert department.department_id == "dept-csc"

    def test_code_is_normalised_for_downstream_matric_numbers(self) -> None:
        assert Department("dept-csc", "fac-sci", "Computer Science", "csc").code == "CSC"

    @pytest.mark.parametrize("blank", ["", "  "])
    def test_cannot_be_built_without_a_faculty(self, blank: str) -> None:
        with pytest.raises(MissingIdentifierError):
            Department("dept-csc", blank, "Computer Science", "CSC")


class TestProgram:
    def test_is_not_admitting_when_created(self) -> None:
        """Admitting is a deliberate act, never a side effect of defining a program."""
        program = Program.create("prog-csc-bsc", "dept-csc", "B.Sc. Computer Science", "CSC-BSC")
        assert program.is_admitting is False

    def test_admissions_can_be_opened_and_closed(self) -> None:
        program = Program.create("prog-csc-bsc", "dept-csc", "B.Sc. Computer Science", "CSC-BSC")

        program.open_admissions()
        assert program.is_admitting is True

        program.close_admissions()
        assert program.is_admitting is False

    def test_opening_an_already_admitting_program_is_idempotent(self) -> None:
        program = Program.create("prog-csc-bsc", "dept-csc", "B.Sc. Computer Science", "CSC-BSC")
        program.open_admissions()
        program.open_admissions()
        assert program.is_admitting is True

    def test_references_its_department_by_id(self) -> None:
        program = Program.create("prog-csc-bsc", "dept-csc", "B.Sc. Computer Science", "CSC-BSC")
        assert program.department_id == "dept-csc"

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_cannot_be_built_without_a_department(self, blank: str) -> None:
        with pytest.raises(MissingIdentifierError):
            Program.create("prog-csc-bsc", blank, "B.Sc. Computer Science", "CSC-BSC")
