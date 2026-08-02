"""Domain exceptions for the Student Profile context.

Every failure this context can express is a named subclass of
:class:`StudentProfileError`. Nothing here raises a bare ``Exception``, and no caller
should have to inspect a message string to tell one failure from another.
"""


class StudentProfileError(Exception):
    """Base class for every Student Profile domain error."""


class MissingIdentifierError(StudentProfileError):
    """A required identifier or name was empty or blank."""


class InvalidDepartmentCodeError(StudentProfileError):
    """A department code was not of the numeric form the matric number requires."""


class InvalidEntryYearError(StudentProfileError):
    """An entry year was not a plausible four-digit year."""


class InvalidLevelError(StudentProfileError):
    """A level was not a positive multiple of 100."""


class InvalidBioDataError(StudentProfileError):
    """Bio-data was incomplete or self-contradictory (a birth date in the future)."""


class InvalidMatricNumberError(StudentProfileError):
    """A matric number was not of the form this context issues."""


class InvalidSequenceStateError(StudentProfileError):
    """A matric sequence was restored from a count that cannot have happened."""
