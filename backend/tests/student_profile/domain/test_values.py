"""The value objects nothing may be constructed around.

These are the guards that make "an entity must never be constructible into an invalid
state" true rather than aspirational, so they are tested for what they *reject* at least
as carefully as for what they accept.
"""

from datetime import date, timedelta

import pytest

from student_profile.domain import (
    BioData,
    DepartmentCode,
    EntryYear,
    InvalidBioDataError,
    InvalidDepartmentCodeError,
    InvalidEntryYearError,
    InvalidLevelError,
    Level,
    MissingIdentifierError,
)


class TestDepartmentCode:
    def test_four_digits_is_the_form_a_matric_number_carries(self) -> None:
        assert DepartmentCode("0591").value == "0591"

    def test_a_leading_zero_is_significant(self) -> None:
        """``0591`` is not 591: the width is what keeps the matric number parseable."""
        assert DepartmentCode("0591") != DepartmentCode("5910")

    @pytest.mark.parametrize("value", ["591", "05910", "", "   "])
    def test_the_wrong_width_is_rejected(self, value: str) -> None:
        with pytest.raises(InvalidDepartmentCodeError):
            DepartmentCode(value)

    @pytest.mark.parametrize("value", ["CSC", "05C1", "59.1", "-591"])
    def test_a_non_numeric_code_is_rejected(self, value: str) -> None:
        """Faculty & Department's alphabetic code never reaches this far untranslated."""
        with pytest.raises(InvalidDepartmentCodeError):
            DepartmentCode(value)

    @pytest.mark.parametrize("value", [591, None, 5.91])
    def test_a_non_string_is_rejected(self, value: object) -> None:
        with pytest.raises(InvalidDepartmentCodeError):
            DepartmentCode(value)  # type: ignore[arg-type]

    def test_two_codes_with_the_same_digits_are_the_same_code(self) -> None:
        assert DepartmentCode("0591") == DepartmentCode("0591")


class TestEntryYear:
    def test_the_year_is_kept_in_full(self) -> None:
        assert EntryYear(2026).value == 2026

    @pytest.mark.parametrize("value", [1899, 3000, -2026, 0])
    def test_an_implausible_year_is_rejected(self, value: int) -> None:
        with pytest.raises(InvalidEntryYearError):
            EntryYear(value)

    @pytest.mark.parametrize("value", ["2026", 2026.0, None, True])
    def test_a_non_integer_year_is_rejected(self, value: object) -> None:
        with pytest.raises(InvalidEntryYearError):
            EntryYear(value)  # type: ignore[arg-type]

    def test_years_order_by_time(self) -> None:
        assert EntryYear(2026) < EntryYear(2027)


class TestLevel:
    @pytest.mark.parametrize("value", [100, 200, 500, 900])
    def test_multiples_of_a_hundred_are_levels(self, value: int) -> None:
        assert Level(value).value == value

    def test_there_is_no_ceiling(self) -> None:
        """How many levels a program runs to is an institutional fact, not ours to guess."""
        assert Level(1000).value == 1000

    @pytest.mark.parametrize("value", [0, 50, 150, -100])
    def test_anything_else_is_not_a_level(self, value: int) -> None:
        with pytest.raises(InvalidLevelError):
            Level(value)

    @pytest.mark.parametrize("value", ["100", 100.0, None, True])
    def test_a_non_integer_level_is_rejected(self, value: object) -> None:
        with pytest.raises(InvalidLevelError):
            Level(value)  # type: ignore[arg-type]


class TestBioData:
    def test_a_name_alone_is_enough_to_describe_a_person(self) -> None:
        """Requiring more would guarantee the missing fields get filled with fiction."""
        bio = BioData(full_name="Adaeze Okonkwo")

        assert bio.full_name == "Adaeze Okonkwo"
        assert bio.date_of_birth is None
        assert bio.email is None
        assert bio.phone_number is None

    def test_surrounding_whitespace_is_not_part_of_a_name(self) -> None:
        assert BioData(full_name="  Chidi Nwosu  ").full_name == "Chidi Nwosu"

    @pytest.mark.parametrize("value", ["", "   ", None, 42])
    def test_a_missing_name_is_rejected(self, value: object) -> None:
        with pytest.raises(MissingIdentifierError):
            BioData(full_name=value)  # type: ignore[arg-type]

    @pytest.mark.parametrize("field", ["email", "phone_number"])
    def test_an_optional_field_may_be_absent_but_not_blank(self, field: str) -> None:
        assert getattr(BioData(full_name="Chidi Nwosu", **{field: None}), field) is None

        with pytest.raises(MissingIdentifierError):
            BioData(full_name="Chidi Nwosu", **{field: "   "})

    @pytest.mark.parametrize("value", ["chidi@lasu.edu.ng", "not-an-email", "+2348012345678"])
    def test_no_format_is_imposed_on_contact_details(self, value: str) -> None:
        """A guessed pattern would start rejecting real students. Only blankness is ours."""
        assert BioData(full_name="Chidi Nwosu", email=value).email == value

    def test_a_birth_date_in_the_past_is_kept(self) -> None:
        born = date(2008, 4, 17)

        assert BioData(full_name="Chidi Nwosu", date_of_birth=born).date_of_birth == born

    @pytest.mark.parametrize("days", [0, 1, 365])
    def test_nobody_is_born_today_or_later(self, days: int) -> None:
        with pytest.raises(InvalidBioDataError):
            BioData(full_name="Chidi Nwosu", date_of_birth=date.today() + timedelta(days=days))

    def test_a_birth_date_that_is_not_a_date_is_rejected(self) -> None:
        with pytest.raises(InvalidBioDataError):
            BioData(full_name="Chidi Nwosu", date_of_birth="2008-04-17")  # type: ignore[arg-type]
