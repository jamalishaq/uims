"""The applicants for one program — the list a registrar actually works through.

**Keyed on the applied program**, which is the decision worth restating here rather than
leaving in a commit message. An ``Applicant`` carries two program ids and either could key
this list:

* *applied* — the people who wanted to come here. Stable: it never changes, so a registrar's
  list does not silently lose somebody the moment the offer flow places them elsewhere.
* *offered* — the people who will actually arrive. Useful, and a different report.

The registrar's working list is the first, because their job is deciding about the people in
front of them. Somebody placed here from another program's fallback chain shows up in the
*capacity* half of the dashboard (``offers_made``), not in this list — see
``SummariseProgramAdmissions`` on why the two populations do not reconcile.

``status`` filters the list because the useful view is almost never all of it: the work is the
screened-and-waiting, and the archive is everybody else.
"""

from dataclasses import dataclass

from admissions.application.errors import UnknownApplicationStatusError
from admissions.domain.applicant import Applicant, ApplicationStatus
from admissions.ports.applicant_repository import ApplicantRepositoryPort


@dataclass(frozen=True)
class ListProgramApplicantsCommand:
    """Which program's applicants to list, optionally narrowed to one status.

    ``status`` is the enum's wire value (``"screened"``), not the enum, because a command is
    what crosses from a transport. An unrecognised value raises in the use case rather than
    silently matching nobody, which would look like an empty cohort.
    """

    program_id: str
    session_id: str
    status: str | None = None


class ListProgramApplicants:
    """List everyone who applied to a program, newest state included."""

    def __init__(self, applicants: ApplicantRepositoryPort) -> None:
        self._applicants = applicants

    async def execute(self, command: ListProgramApplicantsCommand) -> tuple[Applicant, ...]:
        """Every applicant to the program, in the order the repository holds them.

        Raises:
            UnknownApplicationStatusError: ``status`` is not one of this context's application
                statuses. A filter nobody recognises must not read as "no applicants" — that
                is a typo answering the same as an empty cohort, and a registrar would act on
                it.
        """
        wanted = _status(command.status)
        cohort = await self._applicants.list_for_session(command.session_id)
        return tuple(
            applicant
            for applicant in cohort
            if applicant.applied_program_id == command.program_id
            and (wanted is None or applicant.status is wanted)
        )


def _status(value: str | None) -> ApplicationStatus | None:
    """The status to filter by, or ``None`` for all of them."""
    if value is None:
        return None
    try:
        return ApplicationStatus(value)
    except ValueError as unknown:
        known = ", ".join(status.value for status in ApplicationStatus)
        raise UnknownApplicationStatusError(
            f"{value!r} is not an application status; expected one of {known}"
        ) from unknown
