"""Domain exceptions for the Course Catalog context.

Every failure this context can express is a named subclass of
:class:`CourseCatalogError`. Nothing here raises a bare ``Exception``, and no caller
should have to inspect a message string to tell one failure from another.

There are few of these because there is little to get wrong. A catalog of courses is
slow-changing reference data (CLAUDE.md section 3): almost every rule worth having
about a course — may this student take it, does it clash, is it full — belongs to
Enrollment, which owns the judgment. What is left here is that a course must be
described completely, and that a course cannot be its own prerequisite.
"""


class CourseCatalogError(Exception):
    """Base class for every Course Catalog domain error."""


class MissingIdentifierError(CourseCatalogError):
    """A required identifier, code, or title was empty or blank."""


class InvalidCreditUnitsError(CourseCatalogError):
    """Credit units were not a whole number of units, one or more."""


class SelfPrerequisiteError(CourseCatalogError):
    """A course was asked to require itself."""


class DuplicatePrerequisiteError(CourseCatalogError):
    """A course already requires the given prerequisite."""


class PrerequisiteNotRequiredError(CourseCatalogError):
    """A prerequisite was withdrawn from a course that never required it."""


class PrerequisiteCycleError(CourseCatalogError):
    """Adding a prerequisite would make a course require itself indirectly."""
