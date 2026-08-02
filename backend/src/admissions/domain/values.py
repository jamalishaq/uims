"""Value objects and the shared construction guards used across this context.

The guards live here so that "an entity must never be constructible into an invalid
state" is enforced in one place rather than restated in every constructor.

They duplicate the guards in Faculty & Department, Course Catalog and Student Profile by
design, not by oversight. A context may not import another context's domain models
(CLAUDE.md section 4), and the architecture fitness test enforces it. Two contexts
agreeing today about what a blank identifier is does not mean they must agree forever —
the duplication is what lets either one change its mind. ``BioData`` is the sharpest
example: Student Profile holds the bio-data of people who are already students, and
Admissions holds the bio-data of people who may never become one. They are the same
fields today and are not the same concept.

What this module deliberately does not do is judge a UTME result. Whether these four
subjects qualify this applicant for this program is a question about a program's entry
requirement, which is ``SubjectCombinationRule``'s job and reads ``UtmeResult.subjects``
to do it. A value object that knew about programs would have to be reconstructed every
time a requirement changed.
"""

from dataclasses import dataclass
from datetime import date

from admissions.domain.errors import (
    InvalidBioDataError,
    InvalidUtmeResultError,
    InvalidUtmeScoreError,
    MissingIdentifierError,
)

UTME_SUBJECT_COUNT = 4
"""Subjects in a UTME result. Settled institutional fact (CLAUDE.md section 6)."""

MIN_SUBJECT_SCORE = 0
MAX_SUBJECT_SCORE = 100


def require_identifier(value: str, field: str) -> str:
    """Return ``value`` stripped, rejecting anything blank.

    Identifiers minted by other contexts — a program id, a session id — are opaque to us:
    non-emptiness is the only thing we can honestly check.
    """
    if not isinstance(value, str) or not value.strip():
        raise MissingIdentifierError(f"{field} must be a non-empty identifier")
    return value.strip()


def require_text(value: str, field: str) -> str:
    """Return ``value`` stripped, rejecting anything blank."""
    if not isinstance(value, str) or not value.strip():
        raise MissingIdentifierError(f"{field} must be non-empty")
    return value.strip()


def require_optional_text(value: str | None, field: str) -> str | None:
    """Return ``value`` stripped, or ``None``. Absent is fine; blank is not.

    An applicant we hold no phone number for is a normal record. An applicant whose phone
    number is three spaces is a data-entry accident, and storing it would mean every later
    reader has to decide again whether that counts as a phone number.
    """
    if value is None:
        return None
    return require_text(value, field)


@dataclass(frozen=True)
class BioData:
    """Who the applicant is, as far as this context is concerned.

    A name is required; everything else is optional, because a record that cannot be
    created without a phone number is a record that will be created with a fake one.

    No format is imposed on the email address or the phone number. Whether LASU writes
    ``+2348012345678`` or ``08012345678`` is an institutional fact, and a pattern guessed
    here would start rejecting real applicants. The one cross-field check that *is* ours
    to make is that nobody was born in the future.
    """

    full_name: str
    date_of_birth: date | None = None
    email: str | None = None
    phone_number: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "full_name", require_text(self.full_name, "full name"))
        object.__setattr__(self, "email", require_optional_text(self.email, "email"))
        object.__setattr__(
            self, "phone_number", require_optional_text(self.phone_number, "phone number")
        )
        if self.date_of_birth is None:
            return
        if not isinstance(self.date_of_birth, date):
            raise InvalidBioDataError("date of birth must be a date")
        if self.date_of_birth >= date.today():
            raise InvalidBioDataError(f"date of birth {self.date_of_birth} is not in the past")


@dataclass(frozen=True)
class UtmeSubjectScore:
    """One subject an applicant sat, and what they scored in it.

    The subject name is upper-cased so that ``"Use of English"`` and ``"USE OF ENGLISH"``
    are one subject rather than two — an applicant cannot be allowed to satisfy a
    requirement twice by varying the capitalisation. No vocabulary of subject names is
    imposed: which subjects JAMB offers is an institutional fact that changes without
    asking this codebase.
    """

    subject: str
    score: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "subject", require_text(self.subject, "subject").upper())
        if not isinstance(self.score, int) or isinstance(self.score, bool):
            raise InvalidUtmeScoreError(f"score for {self.subject} must be an integer")
        if not MIN_SUBJECT_SCORE <= self.score <= MAX_SUBJECT_SCORE:
            raise InvalidUtmeScoreError(
                f"score {self.score} for {self.subject} is outside "
                f"{MIN_SUBJECT_SCORE}-{MAX_SUBJECT_SCORE}"
            )

    def __str__(self) -> str:
        return f"{self.subject} {self.score}"


@dataclass(frozen=True)
class UtmeResult:
    """An applicant's UTME performance: four distinct subjects, each scored out of 100.

    The count is fixed rather than open because a result carrying three subjects is not a
    result — it is a half-entered form, and admitting one means every screening rule
    downstream has to decide for itself what a missing subject means. The distinctness
    check is the same argument: a result listing Chemistry twice would let one score be
    counted against two requirements.

    ``aggregate`` is derived, never stored. A stored total is a second source of truth
    that can drift from the scores it claims to summarise.
    """

    scores: tuple[UtmeSubjectScore, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "scores", tuple(self.scores))
        if any(not isinstance(score, UtmeSubjectScore) for score in self.scores):
            raise InvalidUtmeResultError("a UTME result is made of UtmeSubjectScore values")
        if len(self.scores) != UTME_SUBJECT_COUNT:
            raise InvalidUtmeResultError(
                f"a UTME result has exactly {UTME_SUBJECT_COUNT} subjects, got {len(self.scores)}"
            )
        subjects = [score.subject for score in self.scores]
        if len(set(subjects)) != len(subjects):
            raise InvalidUtmeResultError(f"UTME subjects must be distinct, got {subjects}")

    @property
    def subjects(self) -> frozenset[str]:
        """The subjects sat, for ``SubjectCombinationRule`` to check a requirement against."""
        return frozenset(score.subject for score in self.scores)

    @property
    def aggregate(self) -> int:
        """The total across all subjects, the number an admissions board ranks on."""
        return sum(score.score for score in self.scores)

    def score_for(self, subject: str) -> int | None:
        """What the applicant scored in ``subject``, or ``None`` if they did not sit it."""
        wanted = require_text(subject, "subject").upper()
        for score in self.scores:
            if score.subject == wanted:
                return score.score
        return None

    def __str__(self) -> str:
        return f"{', '.join(str(score) for score in self.scores)} ({self.aggregate})"
