"""Outbound port for the fee schedules this context publishes and reads."""

from abc import ABC, abstractmethod

from billing.domain.fee_schedule import FeeSchedule


class FeeScheduleRepositoryPort(ABC):
    """Persistence for :class:`FeeSchedule`, keyed by ``session_id``.

    Billing-owned policy data, in the manner of Admissions' entry-requirement repository:
    fees are published for a session by somebody entitled to set them, and last session's
    schedule stays readable after this session's is published. An account charged in 2026 was
    charged against the 2026 schedule, and a repository that overwrote would leave nobody able
    to say what.
    """

    @abstractmethod
    def add(self, schedule: FeeSchedule) -> None:
        """Publish a session's fees.

        Raises:
            DuplicateAggregateError: a schedule is already published for that session.
        """

    @abstractmethod
    def save(self, schedule: FeeSchedule) -> None:
        """Persist changes to a schedule that is already published.

        Note that re-publishing at a new figure does not re-price bills already raised: the
        account refuses to change a charge that already stands, so a correction is an
        administrative act rather than a side effect of editing a schedule.

        Raises:
            AggregateNotFoundError: no schedule was ever published for that session.
        """

    @abstractmethod
    def get(self, session_id: str) -> FeeSchedule | None:
        """Return the session's schedule, or ``None`` if none has been published.

        ``None`` means different things to the two callers, and each decides for itself:
        opening an account refuses it, because an offer with no acceptance fee gates
        matriculation on nothing; the session-fee batch has nothing to apply and says so.
        """
