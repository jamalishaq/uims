"""The one place a matric number comes into existence.

Student Profile owns matric number issuance (CLAUDE.md section 3), and there are two
ways a student is created: an administrator registering one by hand, and Admissions
announcing ``StudentMatriculated``. Both go through this service. That is the whole
reason it exists as a service rather than as a couple of lines in a use case — two
call sites formatting their own numbers would drift, and the drift would not show up
until a student from one path and a student from the other collided or, more quietly,
sorted differently.

The service is stateless. The state that matters — how many numbers a department has
issued this year — belongs to the :class:`MatricSequence` aggregate, which is loaded
and stored through a port, so it survives a restart. An issuer that kept its own
counters would start again from 001 every time the process came up and re-issue numbers
that living students already hold.
"""

from student_profile.domain.matric_number import MatricNumber, MatricNumberFormat
from student_profile.domain.matric_sequence import MatricSequence


class MatricNumberIssuer:
    """Issues matric numbers against a department's per-year sequence."""

    def __init__(self, matric_format: MatricNumberFormat | None = None) -> None:
        self._format = matric_format or MatricNumberFormat()

    @property
    def format(self) -> MatricNumberFormat:
        return self._format

    def issue(self, sequence: MatricSequence) -> MatricNumber:
        """Claim the next number for the sequence's department and year.

        The sequence carries both format inputs, so a caller cannot ask for a number
        formatted with one department's code but drawn from another's counter.

        The ordinal is claimed before the number is composed, and claiming is permanent:
        if the caller then fails to store the student, the number is burnt rather than
        handed to somebody else.
        """
        ordinal = sequence.take_next()
        return self._format.render(sequence.department_code, sequence.entry_year, ordinal)
