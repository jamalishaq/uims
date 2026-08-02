"""Failures that belong to orchestration rather than to the domain.

"Faculty & Department has never heard of that program" is not a rule about how a
university works — it is a statement about what the system currently holds. Keeping these
separate from :class:`StudentProfileError` means a caller can tell a business rejection
("that is not a valid level") from a lookup miss without reading a message string.
"""


class ApplicationError(Exception):
    """Base class for every Student Profile use-case error."""


class ProgramPlacementUnknownError(ApplicationError):
    """Faculty & Department could not say which department and year a placement means.

    Without both, no matric number can be composed, so registration stops here rather
    than inventing a code or a year. Raised for an unknown program, an unknown session,
    or a program that context does not consider part of that session.
    """
