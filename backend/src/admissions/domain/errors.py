"""Domain exceptions for the Admissions context.

Every failure this context can express is a named subclass of :class:`AdmissionsError`.
Nothing here raises a bare ``Exception``, and no caller should have to inspect a message
string to tell one failure from another.

There are more of these than in the other contexts because Admissions is the one place
that owns a real lifecycle. An applicant moves through six months of decisions made by
different people — a screening officer, an admissions board, the applicant themselves, a
bursary confirming a payment, a registrar matriculating — and each of those hands can
arrive at the wrong moment. Naming every wrong moment separately is what lets a use case
answer "why not?" without parsing prose.

Note what is *not* here. Quota exhaustion is a normal domain outcome rather than an error
(CLAUDE.md section 3), and so is a screening that finds an applicant unqualified. An
error means the caller asked for something the aggregate cannot do; those two mean the
answer was legitimately no.
"""


class AdmissionsError(Exception):
    """Base class for every Admissions domain error."""


class MissingIdentifierError(AdmissionsError):
    """A required identifier or text field was empty or blank."""


class InvalidBioDataError(AdmissionsError):
    """An applicant's bio-data field was missing or not what it claimed to be."""


class InvalidUtmeScoreError(AdmissionsError):
    """A UTME subject score was not a whole number within the permitted range."""


class InvalidUtmeResultError(AdmissionsError):
    """A UTME result was not the required number of distinct subject scores."""


class ApplicantAlreadyScreenedError(AdmissionsError):
    """Screening has already been performed for this applicant."""


class ApplicantNotScreenedError(AdmissionsError):
    """The operation requires an applicant who has been screened."""


class OfferAlreadyMadeError(AdmissionsError):
    """The applicant's application has already been decided one way or the other."""


class NoOfferToRespondToError(AdmissionsError):
    """There is no outstanding offer for the applicant to accept or decline."""


class OfferAlreadyRespondedToError(AdmissionsError):
    """The applicant has already responded to their offer."""


class OfferNotAcceptedError(AdmissionsError):
    """The operation requires an applicant who has accepted their offer."""


class AcceptanceFeeNotClearedError(AdmissionsError):
    """Matriculation was attempted before the acceptance fee cleared."""


class ApplicationOutcomeFinalError(AdmissionsError):
    """The application has reached a terminal outcome and cannot change."""
