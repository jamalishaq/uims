"""Enrollment application layer.

One use case: ``RegisterForCourse``. It gathers facts through the ports and asks the domain
whether they add up, which is the whole of what an application service is allowed to do
here — every rule it appears to enforce is enforced somewhere in ``domain/``, and this
layer only decides *what to ask next* and *in what order to write*.

Refusals come back as values, not exceptions. ``RegistrationAccepted`` and
``RegistrationRefused`` are both ordinary answers, and only two things raise: a course
Course Catalog has never heard of, and a course nobody is running this term. Both are
questions that cannot be answered rather than answers of no.

The transitions that follow registration — ``await_grade`` and ``finalize`` — are on the
aggregate and have no use case yet. They will be driven by Academic Records' grade flow in
Phase 4.2, and inventing an administrative use case for them now would be inventing who is
allowed to press the button.
"""

from enrollment.application.errors import (
    ApplicationError,
    CourseNotFoundError,
    CourseOfferingNotFoundError,
)
from enrollment.application.register_for_course import (
    RegisterForCourse,
    RegisterForCourseCommand,
    RegistrationAccepted,
    RegistrationOutcome,
    RegistrationRefused,
)

__all__ = [
    "ApplicationError",
    "CourseNotFoundError",
    "CourseOfferingNotFoundError",
    "RegisterForCourse",
    "RegisterForCourseCommand",
    "RegistrationAccepted",
    "RegistrationOutcome",
    "RegistrationRefused",
]
