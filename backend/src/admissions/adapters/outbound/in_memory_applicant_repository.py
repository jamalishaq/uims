"""Dict-backed ``ApplicantRepositoryPort``."""

from admissions.adapters.outbound._store import InMemoryStore
from admissions.domain.applicant import Applicant
from admissions.ports.applicant_repository import ApplicantRepositoryPort


class InMemoryApplicantRepository(ApplicantRepositoryPort):
    """Holds applications in memory for the duration of the process."""

    def __init__(self) -> None:
        self._store = InMemoryStore[Applicant](
            "applicant", lambda applicant: applicant.applicant_id
        )

    async def add(self, applicant: Applicant) -> None:
        self._store.add(applicant)

    async def save(self, applicant: Applicant) -> None:
        self._store.save(applicant)

    async def get(self, applicant_id: str) -> Applicant | None:
        return self._store.get(applicant_id)

    async def list_for_session(self, session_id: str) -> tuple[Applicant, ...]:
        return tuple(
            applicant for applicant in self._store.all() if applicant.session_id == session_id
        )
