"""Failures that belong to orchestration rather than to the domain.

A use case can fail in ways no aggregate has an opinion about: it was asked about somebody
who is not stored, or the policy it needs to do its job was never published. Neither is an
``AdmissionsError``, because neither is an applicant or a program doing something it may
not do.

Note what is not in here. An applicant whose subjects do not qualify them is *not* an
error at any layer — screening returns ``ApplicantNotQualified`` and the application ends
with no offer available. That is the university answering no, which it does to most
applicants, and a use case that raised on it would make the ordinary path of admissions
run on exceptions.
"""


class ApplicationError(Exception):
    """Base class for every Admissions use-case error."""


class ApplicantNotFoundError(ApplicationError):
    """No application is stored under the given applicant id."""


class EntryRequirementNotFoundError(ApplicationError):
    """No entry requirement has been published for that program and session.

    Deliberately an error and not a screening outcome. An unqualified applicant means the
    university looked at a rule and said no; a missing rule means nobody wrote one down,
    and screening against it regardless would quietly turn away everyone who applied to
    that program — a data-entry omission wearing the clothes of an admissions decision.
    """
