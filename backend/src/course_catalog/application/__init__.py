"""Course Catalog application layer.

Reference-data CRUD and nothing else. Every use case here loads through a port,
delegates each decision to the domain, and persists — the rules about codes, credit
units and prerequisites are stated once, in ``domain/``, and never restated here.

Domain errors pass through untranslated: :class:`SelfPrerequisiteError` reaching a
caller unchanged is the point, because the domain has already said exactly what went
wrong and rewrapping it would only lose that.
"""

from course_catalog.application.add_prerequisite import AddPrerequisite, AddPrerequisiteCommand
from course_catalog.application.amend_course import AmendCourse, AmendCourseCommand
from course_catalog.application.errors import (
    ApplicationError,
    CourseNotFoundError,
    DuplicateCourseCodeError,
    PrerequisiteCourseNotFoundError,
)
from course_catalog.application.list_department_courses import (
    ListDepartmentCourses,
    ListDepartmentCoursesCommand,
)
from course_catalog.application.read_course import ReadCourse, ReadCourseCommand
from course_catalog.application.read_prerequisite_chain import (
    ReadPrerequisiteChain,
    ReadPrerequisiteChainCommand,
)
from course_catalog.application.register_course import RegisterCourse, RegisterCourseCommand
from course_catalog.application.reinstate_course import ReinstateCourse, ReinstateCourseCommand
from course_catalog.application.remove_prerequisite import (
    RemovePrerequisite,
    RemovePrerequisiteCommand,
)
from course_catalog.application.retire_course import RetireCourse, RetireCourseCommand
from course_catalog.application.views import CourseView

__all__ = [
    "AddPrerequisite",
    "AddPrerequisiteCommand",
    "AmendCourse",
    "AmendCourseCommand",
    "ApplicationError",
    "CourseNotFoundError",
    "CourseView",
    "DuplicateCourseCodeError",
    "ListDepartmentCourses",
    "ListDepartmentCoursesCommand",
    "PrerequisiteCourseNotFoundError",
    "ReadCourse",
    "ReadCourseCommand",
    "ReadPrerequisiteChain",
    "ReadPrerequisiteChainCommand",
    "RegisterCourse",
    "RegisterCourseCommand",
    "ReinstateCourse",
    "ReinstateCourseCommand",
    "RemovePrerequisite",
    "RemovePrerequisiteCommand",
    "RetireCourse",
    "RetireCourseCommand",
]
