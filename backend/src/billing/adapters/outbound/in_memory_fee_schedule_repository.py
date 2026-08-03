"""Dict-backed ``FeeScheduleRepositoryPort``, keyed by ``session_id``."""

from billing.adapters.outbound._store import InMemoryStore
from billing.domain.fee_schedule import FeeSchedule
from billing.ports.fee_schedule_repository import FeeScheduleRepositoryPort


class InMemoryFeeScheduleRepository(FeeScheduleRepositoryPort):
    """Holds published fee schedules in memory for the duration of the process."""

    def __init__(self) -> None:
        self._store = InMemoryStore[FeeSchedule](
            "fee schedule", lambda schedule: schedule.session_id
        )

    def add(self, schedule: FeeSchedule) -> None:
        self._store.add(schedule)

    def save(self, schedule: FeeSchedule) -> None:
        self._store.save(schedule)

    def get(self, session_id: str) -> FeeSchedule | None:
        return self._store.get(session_id)

    def all(self) -> tuple[FeeSchedule, ...]:
        """Every schedule published, in the order published.

        Not on the port: the two use cases each read one session's schedule, and a port method
        that returned all of them would be an invitation to compare sessions in code that has
        no business doing so. It is here because a test — and, later, an administrative screen
        — wants to see what has been published.
        """
        return self._store.all()
