"""Failures that belong to orchestration rather than to the domain.

"No lecturer with that id" is not a rule about how a university works — it is a
statement about what this system currently holds. Keeping these separate from
:class:`FacultyDepartmentError` means a caller can tell a business rejection ("you do not
teach this course") from a lookup miss ("we have never heard of you") without reading a
message string.
"""


class ApplicationError(Exception):
    """Base class for every Faculty & Department use-case error."""


class LecturerNotFoundError(ApplicationError):
    """No lecturer is stored under the given identifier."""


class SessionNotFoundError(ApplicationError):
    """No academic session is stored under the given identifier."""


class FacultyNotFoundError(ApplicationError):
    """No faculty is stored under the given identifier.

    Raised when a department names a faculty nobody has. Creating it anyway would leave the
    structure with a dangling reference that only shows up much later, as a program whose
    placement cannot be read — and ``ReadProgramPlacement`` answers ``None`` for that, so the
    failure would surface as an applicant being told their program does not exist.
    """


class DepartmentNotFoundError(ApplicationError):
    """No department is stored under the given identifier.

    Raised when a program or a lecturer names a department nobody has, for
    :class:`FacultyNotFoundError`'s reason.
    """


class ProgramNotFoundError(ApplicationError):
    """No program is stored under the given identifier."""


class InvalidRankError(ApplicationError):
    """A rank or employment status was named that this university does not have.

    An error rather than a silently dropped field: a rank discarded on the way in would leave
    the record saying nothing, which reads identically to nobody having filled it in — and the
    person who typed it would have no way to tell.
    """
