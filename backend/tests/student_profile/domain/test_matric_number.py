"""How a matric number is spelled, and the fact that only one thing decides it.

The format is an institutional fact (CLAUDE.md section 6): LASU writes ``260591001`` —
two digits of entry year, four of department code, then the student's place in that
department's intake for that year. These tests pin that shape, because a silent change to
it would leave two generations of students whose numbers cannot be told apart.
"""

import pytest

from student_profile.domain import (
    DepartmentCode,
    EntryYear,
    InvalidMatricNumberError,
    MatricNumber,
    MatricNumberFormat,
)

CSC = DepartmentCode("0591")
YEAR_2026 = EntryYear(2026)


class TestMatricNumber:
    def test_a_matric_number_is_a_run_of_digits(self) -> None:
        assert MatricNumber("260591001").value == "260591001"

    @pytest.mark.parametrize("value", ["26/0591/001", "26 0591 001", "CSC2026001", "26059100a"])
    def test_anything_but_digits_is_rejected(self, value: str) -> None:
        with pytest.raises(InvalidMatricNumberError):
            MatricNumber(value)

    @pytest.mark.parametrize("value", ["", "   ", None, 260591001])
    def test_an_empty_or_non_string_value_is_rejected(self, value: object) -> None:
        with pytest.raises(InvalidMatricNumberError):
            MatricNumber(value)  # type: ignore[arg-type]

    def test_two_numbers_with_the_same_digits_are_the_same_number(self) -> None:
        """Equality is the whole reason this is a value object and not a string."""
        assert MatricNumber("260591001") == MatricNumber("260591001")
        assert MatricNumber("260591001") != MatricNumber("260591002")


class TestRendering:
    def test_the_lasu_form(self) -> None:
        assert MatricNumberFormat().render(CSC, YEAR_2026, 1) == MatricNumber("260591001")

    def test_the_sequence_is_padded_to_three_digits(self) -> None:
        rendered = MatricNumberFormat().render(CSC, YEAR_2026, 42)

        assert rendered == MatricNumber("260591042")

    def test_the_year_contributes_only_its_last_two_digits(self) -> None:
        assert MatricNumberFormat().render(CSC, EntryYear(2007), 1) == MatricNumber("070591001")

    def test_the_department_code_keeps_its_leading_zero(self) -> None:
        """Fixed widths are what let the fields be read back out of one run of digits."""
        assert MatricNumberFormat().render(CSC, YEAR_2026, 1).value[2:6] == "0591"

    def test_the_thousandth_student_widens_rather_than_wrapping(self) -> None:
        """Refusing to matriculate them would be the worse failure, and the leading
        fields are fixed-width, so a longer tail is still unambiguous."""
        assert MatricNumberFormat().render(CSC, YEAR_2026, 1000) == MatricNumber("2605911000")

    @pytest.mark.parametrize("sequence", [0, -1, "1", 1.0, None, True])
    def test_a_sequence_that_is_not_a_place_in_an_intake_is_rejected(
        self, sequence: object
    ) -> None:
        """Zero in particular: that is a counter read before it was incremented."""
        with pytest.raises(InvalidMatricNumberError):
            MatricNumberFormat().render(CSC, YEAR_2026, sequence)  # type: ignore[arg-type]


class TestFormatIsAValueNotAConstant:
    """The widths live in a value object so a format change is a construction argument.

    LASU's format is the default; these prove nothing above the format has to know it.
    """

    def test_a_four_digit_year_and_wider_sequence(self) -> None:
        wide = MatricNumberFormat(year_digits=4, sequence_digits=4)

        assert wide.render(CSC, YEAR_2026, 7) == MatricNumber("202605910007")

    def test_two_formats_with_the_same_widths_are_equal(self) -> None:
        assert MatricNumberFormat() == MatricNumberFormat(year_digits=2, sequence_digits=3)

    @pytest.mark.parametrize("widths", [{"year_digits": 0}, {"sequence_digits": -1}])
    def test_a_field_narrower_than_one_digit_is_not_a_format(self, widths: dict[str, int]) -> None:
        with pytest.raises(InvalidMatricNumberError):
            MatricNumberFormat(**widths)

    def test_a_year_cannot_contribute_more_digits_than_it_has(self) -> None:
        with pytest.raises(InvalidMatricNumberError):
            MatricNumberFormat(year_digits=5)
