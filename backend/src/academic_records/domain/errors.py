"""Domain exceptions for the Academic Records context.

Every failure this context can express is a named subclass of
:class:`AcademicRecordsError`. Nothing here raises a bare ``Exception``, and no caller
should have to read a message string to tell one failure from another.

Note what *is* here that the neighbouring contexts would have made an outcome. A full
course offering and a quota-exhausted admission cycle are ordinary answers, so Enrollment
and Admissions signal them as values. A second, different grade arriving for a course a
student has already been graded on is not an ordinary answer: a transcript line has been
recorded and something is now trying to overwrite it. That is
:class:`GradeAlreadyRecordedError`, and it is an error precisely so that a caller cannot
handle it by accident — the only way past it is the correction use case, which requires a
reason and a name.
"""


class AcademicRecordsError(Exception):
    """Base class for every Academic Records domain error."""


class MissingIdentifierError(AcademicRecordsError):
    """A required identifier or text field was empty or blank."""


class InvalidScoreError(AcademicRecordsError):
    """A raw score was not a whole number within the examinable range."""


class InvalidCreditUnitsError(AcademicRecordsError):
    """A course's credit units were not a whole, positive number."""


class InvalidGradingScaleError(AcademicRecordsError):
    """A grading scale's bands overlap, leave a gap, or do not cover the whole score range."""


class InvalidProbationPolicyError(AcademicRecordsError):
    """A probation policy was given a threshold that is not a usable grade point average."""


class GradeAlreadyRecordedError(AcademicRecordsError):
    """A different grade already stands for this course in this semester.

    Recorded grades are final (CLAUDE.md section 3). Changing one is an administrative
    act with a reason and an authorizer behind it, not a second delivery of a submission.
    """


class GradeNotRecordedError(AcademicRecordsError):
    """A correction named a course and semester this record holds no grade for."""


class InvalidCorrectionError(AcademicRecordsError):
    """A correction was attempted without a reason, without an authorizer, or changing nothing."""
