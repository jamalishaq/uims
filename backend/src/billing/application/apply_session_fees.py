"""Charge every active account for a session that has just opened.

CLAUDE.md section 3: "On ``SessionOpened``: batch-apply ``FeeSchedule`` (per program/level) to
all active student accounts." The one place in this system where a single event fans out
across every aggregate of a kind, and the reason the loop below is written the way it is.

**One account per transaction.** Each account is raised against and saved on its own, and
nothing spans two (CLAUDE.md section 4). A crash halfway through leaves the first half
charged and the second half not — under-charging rather than double-charging — and a rerun
finishes the job, because raising a charge that already stands is a no-op. The same
sequential-orchestration argument ``MakeOfferToApplicant`` makes about claiming a place before
recording that somebody holds it: given a failure, be wrong in the direction that can be
corrected.

**An unpriced account is skipped, not raised over.** A program and level the schedule does not
list is a combination nobody has priced this session — the argument Admissions makes about a
missing alternative-program policy. Raising would stop the whole cohort being billed over one
gap in a spreadsheet, and the summary names who was skipped so the gap is visible rather than
silent.

**A missing schedule stops the batch.** Unlike a missing line, this is not a gap: it is a
session that opened before anybody set its fees, and a batch that charged nobody would be
indistinguishable from one where nobody was priced. It raises, which on the in-memory bus
takes the publish call down with it — deliberately, in the manner of every other subscriber
there: a failure swallowed here would report a session as opened that no account was ever
billed for.
"""

from dataclasses import dataclass

from billing.application.errors import FeeScheduleNotPublishedError
from billing.domain.outcomes import ChargeRaised
from billing.ports.account_repository import AccountRepositoryPort
from billing.ports.event_publisher import EventPublisherPort
from billing.ports.fee_schedule_repository import FeeScheduleRepositoryPort


@dataclass(frozen=True)
class SessionFeesApplied:
    """What the batch did, party by party.

    Three lists rather than a count, because the interesting question after a batch is never
    "how many" but "which ones" — and in particular which were ``unpriced``, since that is a
    fee schedule with a hole in it and somebody has to go and fill it.
    """

    session_id: str
    charged: tuple[str, ...]
    already_charged: tuple[str, ...]
    unpriced: tuple[str, ...]

    @property
    def considered(self) -> int:
        """How many accounts the batch looked at."""
        return len(self.charged) + len(self.already_charged) + len(self.unpriced)


class ApplySessionFees:
    """Raise this session's fee on every account the schedule prices."""

    def __init__(
        self,
        accounts: AccountRepositoryPort,
        schedules: FeeScheduleRepositoryPort,
        events: EventPublisherPort,
    ) -> None:
        self._accounts = accounts
        self._schedules = schedules
        self._events = events

    def execute(self, session_id: str) -> SessionFeesApplied:
        """Apply the session's schedule to every active account.

        Raises:
            FeeScheduleNotPublishedError: the session has no published fees at all.
        """
        schedule = self._schedules.get(session_id)
        if schedule is None:
            raise FeeScheduleNotPublishedError(
                f"no fee schedule is published for session {session_id!r}, so its fees cannot "
                "be applied to anybody"
            )

        charged: list[str] = []
        already_charged: list[str] = []
        unpriced: list[str] = []

        for account in self._accounts.all_active():
            fee = schedule.session_fee_for(account.program_id, account.level)
            if fee is None:
                unpriced.append(account.party_id)
                continue

            outcome = account.raise_session_fee(schedule.session_id, fee)
            if isinstance(outcome, ChargeRaised):
                self._accounts.save(account)
                charged.append(account.party_id)
                for event in outcome.events:
                    self._events.publish(event)
            else:
                already_charged.append(account.party_id)

        return SessionFeesApplied(
            session_id=schedule.session_id,
            charged=tuple(charged),
            already_charged=tuple(already_charged),
            unpriced=tuple(unpriced),
        )
