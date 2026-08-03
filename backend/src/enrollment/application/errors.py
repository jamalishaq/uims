"""Failures that belong to orchestration rather than to the domain.

A use case can fail in ways no aggregate has an opinion about: it was asked about a course
Course Catalog does not recognise, or a course nobody is running this term. Neither is an
``EnrollmentError``, because neither is a student or a course doing something it may not
do — they are questions that cannot be answered rather than answers of no.

Note what is not in here, which is most of what this context refuses. A student who has not
passed a prerequisite, who is at their credit cap, who is not financially cleared, or who
wants a seat that is gone, is *not* an error at any layer: ``RegisterForCourse`` returns
``RegistrationRefused`` carrying every reason. That is the university answering no, which
it does to a good number of registration attempts, and a use case that raised on it would
make the ordinary path of registration run on exceptions.
"""


class ApplicationError(Exception):
    """Base class for every Enrollment use-case error."""


class CourseNotFoundError(ApplicationError):
    """Course Catalog does not recognise the course a registration names.

    An unrecognised id is not a refusal, because there is nothing to refuse: no
    prerequisite list to check, no units to count against a cap, no course to be full. A
    retired course is the opposite — it is a real course, and declining to register anybody
    for it is a decision, so it comes back as an ``EligibilityFailure`` instead.
    """


class CourseOfferingNotFoundError(ApplicationError):
    """Nobody opened this course for registration in this term.

    Deliberately an error and not a refusal, and the line is the same one Admissions draws
    around a missing ``AdmissionCycle``: without an offering there is no capacity to check
    and no seat to claim, so the question cannot be answered at all. A course that *is*
    being run and has no seats left is a refusal, and says so with a number attached.
    """
