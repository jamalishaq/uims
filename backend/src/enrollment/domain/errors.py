"""Domain exceptions for the Enrollment context.

Every failure this context can express is a named subclass of :class:`EnrollmentError`.
Nothing here raises a bare ``Exception``, and no caller should have to inspect a message
string to tell one failure from another.

Note what is deliberately *not* here, because it is most of what this context decides.
A student who has not passed a prerequisite, who is already at their credit-load cap, who
has not been cleared by Billing, or who wants a course whose seats are gone is **not** in
an error state — they have asked a question and the answer is no. Those are
``EligibilityFailure`` values and ``CapacityExhausted`` outcomes, and putting them here
would make refusing a registration — the commonest thing this context does — run on
exceptions. An error means the caller asked an aggregate to do something it cannot do:
finalise an enrollment nobody ever registered, build a course offering with a negative
capacity, name a course with an empty id.
"""


class EnrollmentError(Exception):
    """Base class for every Enrollment domain error."""


class MissingIdentifierError(EnrollmentError):
    """A required identifier or text field was empty or blank."""


class InvalidCreditUnitsError(EnrollmentError):
    """A course's credit units were not a whole, positive number."""


class InvalidCapacityError(EnrollmentError):
    """A course offering's capacity was not a whole, non-negative number of seats."""


class InvalidSeatsTakenError(EnrollmentError):
    """An offering was built with a seat count that is negative or already past capacity."""


class InvalidTermError(EnrollmentError):
    """A registration period was built without a proper semester ordinal."""


class InvalidCreditLoadPolicyError(EnrollmentError):
    """A credit-load policy was given a cap that is not a whole, positive number of units."""


class EnrollmentNotRegisteredError(EnrollmentError):
    """The operation requires an enrollment that is still awaiting the end of teaching."""


class EnrollmentNotAwaitingGradeError(EnrollmentError):
    """Finalisation was attempted on an enrollment that is not waiting for its grade."""


class EnrollmentAlreadyFinalizedError(EnrollmentError):
    """The enrollment has been finalised and cannot change."""
