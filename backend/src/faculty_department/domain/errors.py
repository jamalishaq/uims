"""Domain exceptions for the Faculty & Department context.

Every failure this context can express is a named subclass of
:class:`FacultyDepartmentError`. Nothing here raises a bare ``Exception``, and no
caller should have to inspect a message string to tell one failure from another.
"""


class FacultyDepartmentError(Exception):
    """Base class for every Faculty & Department domain error."""


class MissingIdentifierError(FacultyDepartmentError):
    """A required identifier or name was empty or blank."""


class InvalidAcademicYearError(FacultyDepartmentError):
    """An academic year was not a plausible four-digit starting year."""


class InvalidScoreError(FacultyDepartmentError):
    """A submitted score fell outside the permitted 0-100 range."""


class InvalidSemesterSetError(FacultyDepartmentError):
    """A session was given something other than one first and one second semester."""


class SessionAlreadyOpenError(FacultyDepartmentError):
    """An already-open session cannot be opened again."""


class SessionAlreadyClosedError(FacultyDepartmentError):
    """A closed session is terminal: it cannot be reopened or closed twice."""


class SessionNotOpenError(FacultyDepartmentError):
    """The operation requires a session that is currently open."""


class SemesterNotInSessionError(FacultyDepartmentError):
    """The semester does not belong to the session it was used with."""


class DuplicateCourseAssignmentError(FacultyDepartmentError):
    """The lecturer already holds this course for this session."""


class LecturerNotAssignedToCourseError(FacultyDepartmentError):
    """The lecturer does not teach this course in this session."""
