"""Failures that belong to orchestration rather than to the domain.

"No course with that id" is not a rule about how a university works — it is a
statement about what this system currently holds. Keeping these separate from
:class:`CourseCatalogError` means a caller can tell a business rejection ("a course
cannot require itself") from a lookup miss ("we have never heard of that course")
without reading a message string.

:class:`DuplicateCourseCodeError` sits here rather than in the domain on purpose. No
single ``Course`` can tell whether its code is unique; that is a fact about the whole
catalog, which only a repository can answer.
"""


class ApplicationError(Exception):
    """Base class for every Course Catalog use-case error."""


class CourseNotFoundError(ApplicationError):
    """No course is stored under the given identifier."""


class PrerequisiteCourseNotFoundError(ApplicationError):
    """The course named as a prerequisite is not in the catalog."""


class DuplicateCourseCodeError(ApplicationError):
    """Another course already carries the given code."""
