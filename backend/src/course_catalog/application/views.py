"""Primitives-shaped projections of what this context's use cases return.

``read_course.py`` said the projection would earn its keep "once an HTTP adapter needs a
specific shape, and that adapter does not exist yet". It exists now, so this is that shape.

**Why here rather than in the HTTP adapter.** Flattening a ``Course`` means knowing what a
course *is* — that ``prerequisite_ids`` is a tuple and ``is_active`` is derived rather than
stored. That knowledge belongs to the context that owns the vocabulary. Put it in the transport
and the second transport does it again, and the day a field is added, one of them is not
updated. The architecture fitness test enforces the split from the other side: no module under
``adapters/inbound/http/`` may import ``domain/`` at all, so a route has no way to build one of
these itself.

**Additive.** No use case's return type changes. ``ReadCourse.execute`` still hands back a
``Course``, the tests that assert on it still pass, and a caller that wants primitives asks for
them with ``CourseView.of(...)``. The aggregate remains the thing the application layer works
in; this is only what leaves the building.
"""

from dataclasses import dataclass

from course_catalog.domain.course import Course


@dataclass(frozen=True)
class CourseView:
    """One course, flat, with nothing on it that can change a course.

    Handing out a ``Course`` would hand out ``retire`` and ``add_prerequisite`` along with it,
    which is ``read_account.py``'s argument one context over: a read path that can write is a
    read path somebody eventually writes through.
    """

    course_id: str
    department_id: str
    code: str
    title: str
    credit_units: int
    is_active: bool
    prerequisite_ids: tuple[str, ...]

    @classmethod
    def of(cls, course: Course) -> "CourseView":
        """Project a course. The only place in this context that reads one field by field."""
        return cls(
            course_id=course.course_id,
            department_id=course.department_id,
            code=course.code,
            title=course.title,
            credit_units=course.credit_units,
            is_active=course.is_active,
            prerequisite_ids=course.prerequisite_ids,
        )

    @classmethod
    def of_each(cls, courses: tuple[Course, ...]) -> tuple["CourseView", ...]:
        """Project a listing. ``ListDepartmentCourses`` returns a tuple and so does this."""
        return tuple(cls.of(course) for course in courses)
