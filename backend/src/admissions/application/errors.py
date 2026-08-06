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


class AdmissionCycleNotFoundError(ApplicationError):
    """No admission cycle has been opened for that program and session.

    Raised only for the program an applicant actually applied to. Without it there is no
    quota to check and no place to claim, so the offer flow cannot answer its question at
    all — which is different from answering it with a no. An *alternative* program with no
    cycle is not an error: it is simply not offerable this session, and the flow moves on
    to the next one in the chain.
    """


class ProgramNotFoundError(ApplicationError):
    """Faculty & Department does not recognise the program an application names."""


class UnknownApplicationStatusError(ApplicationError):
    """A caller filtered a list by a status this context does not have.

    An error rather than an empty result, because the two would be indistinguishable to
    whoever asked. A registrar filtering their working list by a mistyped status and being
    shown nobody would reasonably conclude there is nobody to work on.
    """


class ProgramNotAdmittingError(ApplicationError):
    """The program exists but is not taking applications for that session.

    An error rather than an outcome, and the distinction is worth the name: this is a
    submitted form failing validation, not the university considering a candidate and
    deciding against them. Nobody has been assessed, and nothing about the applicant is
    the reason.
    """
