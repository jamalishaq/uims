"""Failures a use case can raise that the domain has no opinion about.

The split is the one Admissions and Enrollment already draw. A domain error means an
aggregate was asked to do something it cannot do — overwrite a recorded grade, correct a
grade that was never recorded. These mean the *orchestration* could not proceed: something
the use case had to load was not there.

Nothing here is a judgement about a student. This context makes exactly one judgement —
whether a CGPA is below the probation threshold — and its answer is a
:class:`~academic_records.domain.probation.Standing`, not an exception.
"""


class AcademicRecordsApplicationError(Exception):
    """Base class for every failure this layer raises on its own account."""


class AcademicRecordNotFoundError(AcademicRecordsApplicationError):
    """No academic record is stored for that student.

    Raised by the use cases that operate on an existing record — a correction, a read.
    Never by grade recording, which opens a record when it finds none: the first grade of a
    student's life must not fail because it is the first.
    """


class CourseCreditsUnavailableError(AcademicRecordsApplicationError):
    """Course Catalog does not know what this course is worth.

    Recording the grade anyway at some default weight would misstate the student's CGPA
    with nothing downstream ever flagging it, so the submission is refused and the fact
    stays uncounted until the catalog is fixed. A grade that failed to record is
    recoverable; a transcript quietly wrong for four years is not.
    """
