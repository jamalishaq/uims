"""What one session costs, per program and level.

Billing-owned policy data, scoped to a session, in the manner of Admissions'
``ProgramEntryRequirement``: fees are set by the university and change between sessions, and
holding last year's schedule alongside this year's is what lets an account charged in 2026
still say what it was charged against. Nothing here is computed and nothing is inferred — a
schedule is published, and every amount on it came from somebody who is entitled to set fees
(CLAUDE.md section 6: fee amounts are institutional facts, not inferable).

Two shapes, because the two kinds of charge behave differently:

* **Admission fees** — the acceptance fee and the matriculation fee — are held per session
  and not per program. They are paid once, by an applicant who at that moment has no level
  and may yet end up on a program other than the one they applied for. Whether LASU varies
  them by program is not stated anywhere, and a key nobody populates is worse than no key at
  all: it would make every schedule assert a distinction the university may not draw.
* **Session fees** are keyed by ``(program_id, level)``, which is what CLAUDE.md section 3
  means by "batch-apply ``FeeSchedule`` (per program/level)". Medicine at 500 level and
  History at 100 do not cost the same, and the pair is the smallest key that can say so.

:meth:`FeeSchedule.session_fee_for` answers ``None`` for a combination the schedule does not
price, and ``None`` is an answer rather than a failure. The batch skips such an account, on
the argument Admissions makes about a missing alternative-program policy: a program with no
published line this session is one nobody has priced yet, and raising would stop the whole
cohort being charged over one gap in a spreadsheet.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from billing.domain.errors import InvalidFeeScheduleError
from billing.domain.values import Level, Money, require_identifier


@dataclass(frozen=True)
class SessionFeeLine:
    """What one session costs a student on one program at one level."""

    program_id: str
    level: Level
    amount: Money

    def __post_init__(self) -> None:
        object.__setattr__(self, "program_id", require_identifier(self.program_id, "program_id"))
        if not isinstance(self.level, Level):
            raise InvalidFeeScheduleError("a fee line's level must be a Level")
        if not isinstance(self.amount, Money):
            raise InvalidFeeScheduleError("a fee line's amount must be Money")
        if self.amount.is_zero:
            raise InvalidFeeScheduleError(
                f"the line for {self.program_id} level {self.level} is for nothing; a program "
                "that charges no session fee should be left off the schedule rather than "
                "priced at zero"
            )

    @property
    def key(self) -> tuple[str, Level]:
        return (self.program_id, self.level)

    def __str__(self) -> str:
        return f"{self.program_id} level {self.level}: {self.amount}"


class FeeSchedule:
    """Every fee one session charges. Published once, read by both of this context's handlers."""

    def __init__(
        self,
        session_id: str,
        *,
        acceptance_fee: Money,
        matriculation_fee: Money,
        session_fees: Iterable[SessionFeeLine] = (),
    ) -> None:
        self._session_id = require_identifier(session_id, "session_id")
        self._acceptance_fee = self._require_admission_fee(acceptance_fee, "acceptance fee")
        self._matriculation_fee = self._require_admission_fee(
            matriculation_fee, "matriculation fee"
        )
        self._session_fees = self._indexed(session_fees)

    @classmethod
    def for_session(
        cls,
        session_id: str,
        *,
        acceptance_fee: Money,
        matriculation_fee: Money,
        session_fees: Iterable[SessionFeeLine] = (),
    ) -> "FeeSchedule":
        """Publish a session's fees.

        A schedule with no session-fee lines at all is legal: the admission fees are what an
        offer needs, and the per-program lines can be published later without invalidating
        the accounts already opened against it.
        """
        return cls(
            session_id,
            acceptance_fee=acceptance_fee,
            matriculation_fee=matriculation_fee,
            session_fees=session_fees,
        )

    @staticmethod
    def _require_admission_fee(amount: Money, field: str) -> Money:
        if not isinstance(amount, Money):
            raise InvalidFeeScheduleError(f"the {field} must be Money")
        if amount.is_zero:
            raise InvalidFeeScheduleError(
                f"the {field} is zero; a charge that demands nothing would settle itself the "
                "moment it was raised, and the acceptance fee gates matriculation"
            )
        return amount

    @staticmethod
    def _indexed(lines: Iterable[SessionFeeLine]) -> dict[tuple[str, Level], Money]:
        """Index the lines, refusing a program and level priced twice.

        A schedule listing one combination at two amounts has no defensible reading: whichever
        the code picked, half the cohort would be charged the figure nobody meant. Catching it
        when the schedule is published beats discovering it in a batch of a thousand accounts.
        """
        indexed: dict[tuple[str, Level], Money] = {}
        for line in lines:
            if not isinstance(line, SessionFeeLine):
                raise InvalidFeeScheduleError("session_fees must be SessionFeeLine values")
            if line.key in indexed:
                raise InvalidFeeScheduleError(
                    f"{line.program_id} level {line.level} is priced twice on this schedule"
                )
            indexed[line.key] = line.amount
        return indexed

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def acceptance_fee(self) -> Money:
        """The gating charge. Settling it publishes ``AcceptanceFeePaid``."""
        return self._acceptance_fee

    @property
    def matriculation_fee(self) -> Money:
        """Raised beside the acceptance fee and gating nothing (CLAUDE.md section 4)."""
        return self._matriculation_fee

    @property
    def session_fee_lines(self) -> tuple[SessionFeeLine, ...]:
        """Every priced combination, in the order published. A tuple: callers cannot add one."""
        return tuple(
            SessionFeeLine(program_id=program_id, level=level, amount=amount)
            for (program_id, level), amount in self._session_fees.items()
        )

    def session_fee_for(self, program_id: str, level: Level) -> Money | None:
        """What this session costs on that program at that level, or ``None`` if unpriced.

        ``None`` is an answer, not a failure — see this module's docstring for why the batch
        skips rather than raises on it.
        """
        program_id = require_identifier(program_id, "program_id")
        if not isinstance(level, Level):
            raise InvalidFeeScheduleError("level must be a Level")
        return self._session_fees.get((program_id, level))

    def __repr__(self) -> str:
        return (
            f"FeeSchedule(session_id={self._session_id!r}, "
            f"acceptance_fee={self._acceptance_fee}, "
            f"matriculation_fee={self._matriculation_fee}, "
            f"session_fee_lines={len(self._session_fees)})"
        )
