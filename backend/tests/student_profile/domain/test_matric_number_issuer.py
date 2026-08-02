"""The issuer: the one implementation both creation paths reach.

There is not much code in it, and that is the finding. Everything the issuer does is
delegated — the counter's invariant to :class:`MatricSequence`, the spelling to
:class:`MatricNumberFormat` — so the tests here are about the *wiring*: that it draws
from the sequence it was handed and cannot be told to spell a number from anywhere else.
"""

from concurrent.futures import ThreadPoolExecutor

from student_profile.domain import (
    DepartmentCode,
    EntryYear,
    MatricNumber,
    MatricNumberFormat,
    MatricNumberIssuer,
    MatricSequence,
)

CSC = DepartmentCode("0591")
MCB = DepartmentCode("0672")
YEAR_2026 = EntryYear(2026)


class TestIssuing:
    def test_the_first_student_of_an_intake(self) -> None:
        issued = MatricNumberIssuer().issue(MatricSequence.start(CSC, YEAR_2026))

        assert issued == MatricNumber("260591001")

    def test_successive_students_of_one_intake_run_in_sequence(self) -> None:
        issuer = MatricNumberIssuer()
        sequence = MatricSequence.start(CSC, YEAR_2026)

        issued = [issuer.issue(sequence).value for _ in range(3)]

        assert issued == ["260591001", "260591002", "260591003"]

    def test_the_number_is_composed_from_the_sequence_and_nothing_else(self) -> None:
        """No department or year argument to get wrong: the counter carries both, so a
        number cannot be spelled with one department's code and drawn from another's."""
        issuer = MatricNumberIssuer()

        assert issuer.issue(MatricSequence.start(MCB, YEAR_2026)).value.startswith("260672")

    def test_the_sequence_is_advanced_by_issuing(self) -> None:
        sequence = MatricSequence.start(CSC, YEAR_2026)
        MatricNumberIssuer().issue(sequence)

        assert sequence.issued == 1

    def test_a_burnt_number_is_not_reissued(self) -> None:
        """Claiming is permanent. A student who is never stored leaves a gap, by design."""
        issuer = MatricNumberIssuer()
        sequence = MatricSequence.start(CSC, YEAR_2026)
        issuer.issue(sequence)  # imagine this registration then fails

        assert issuer.issue(sequence) == MatricNumber("260591002")

    def test_the_format_is_the_one_it_was_built_with(self) -> None:
        issuer = MatricNumberIssuer(MatricNumberFormat(year_digits=4, sequence_digits=4))

        assert issuer.issue(MatricSequence.start(CSC, YEAR_2026)) == MatricNumber("202605910001")

    def test_it_defaults_to_the_lasu_format(self) -> None:
        assert MatricNumberIssuer().format == MatricNumberFormat()


class TestConcurrentIssuance:
    def test_no_number_is_issued_twice(self) -> None:
        """The service-level half of the invariant tested on the aggregate: many callers,
        one sequence, no duplicate — which is what the two creation paths look like when
        they arrive at the same moment."""
        issuer = MatricNumberIssuer()
        sequence = MatricSequence.start(CSC, YEAR_2026)

        with ThreadPoolExecutor(max_workers=16) as pool:
            issued = list(pool.map(lambda _: issuer.issue(sequence).value, range(200)))

        assert len(set(issued)) == 200
        assert max(issued) == "260591200"
