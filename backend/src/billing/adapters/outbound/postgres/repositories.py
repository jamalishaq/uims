"""Billing's three repository ports, against Postgres.

The ledger is the one place in this system where a row is money, so two things get more care
here than anywhere else: every amount goes through ``Money`` on the way back in, and every
entry is restored rather than replayed. ``Account.restore`` and ``PaymentIntent.restore`` say
at length why replaying would be wrong; the short version is that allocation and confirmation
are decisions, and a decision read back from storage is a record, not an instruction to decide
again.
"""

from collections.abc import Mapping, Sequence
from datetime import timedelta
from typing import Any

from sqlalchemy import Row, Table
from sqlalchemy.ext.asyncio import AsyncEngine

from billing.adapters.outbound.postgres import _tables as t
from billing.adapters.outbound.postgres._repository import PostgresRepository
from billing.domain.account import Account
from billing.domain.charge import Charge, ChargeKind
from billing.domain.fee_schedule import FeeSchedule, SessionFeeLine
from billing.domain.payment import Payment
from billing.domain.payment_intent import PaymentIntent, PaymentIntentStatus
from billing.domain.values import Level, Money
from billing.ports.account_repository import AccountRepositoryPort
from billing.ports.fee_schedule_repository import FeeScheduleRepositoryPort
from billing.ports.payment_intent_repository import PaymentIntentRepositoryPort


class PostgresAccountRepository(PostgresRepository[Account], AccountRepositoryPort):
    """Holds ledgers in Postgres, keyed by party and resolvable by either of a party's ids."""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(engine, label="account", table=t.accounts, key=("party_id",))

    @property
    def child_tables(self) -> Sequence[tuple[Table, Sequence[str]]]:
        return ((t.charges, ("party_id",)), (t.payments, ("party_id",)))

    def identity_of(self, aggregate: Account) -> tuple[str]:
        return (aggregate.party_id,)

    def row_of(self, aggregate: Account) -> dict[str, Any]:
        return {
            "party_id": aggregate.party_id,
            "student_id": aggregate.student_id,
            "program_id": aggregate.program_id,
            "level": aggregate.level.value,
            "credit_balance": aggregate.credit_balance.amount,
        }

    def child_rows_of(self, aggregate: Account) -> Mapping[Table, Sequence[dict[str, Any]]]:
        return {
            t.charges: [
                {
                    "party_id": aggregate.party_id,
                    "kind": charge.kind.value,
                    "session_id": charge.session_id,
                    "position": position,
                    "amount": charge.amount.amount,
                    "allocated": charge.allocated.amount,
                }
                for position, charge in enumerate(aggregate.charges)
            ],
            t.payments: [
                {
                    "party_id": aggregate.party_id,
                    "gateway_ref": payment.gateway_ref,
                    "position": position,
                    "amount": payment.amount.amount,
                    "received_at": payment.received_at,
                }
                for position, payment in enumerate(aggregate.payments)
            ],
        }

    def restore(self, row: Row[Any], children: Mapping[Table, Sequence[Row[Any]]]) -> Account:
        charges = sorted(children.get(t.charges, ()), key=lambda child: child.position)
        payments = sorted(children.get(t.payments, ()), key=lambda child: child.position)
        return Account.restore(
            row.party_id,
            row.program_id,
            Level(row.level),
            student_id=row.student_id,
            charges=[
                Charge(
                    kind=ChargeKind(charge.kind),
                    session_id=charge.session_id,
                    amount=Money(charge.amount),
                    allocated=Money(charge.allocated),
                )
                for charge in charges
            ],
            payments=[
                Payment(
                    gateway_ref=payment.gateway_ref,
                    amount=Money(payment.amount),
                    received_at=payment.received_at,
                )
                for payment in payments
            ],
            credit_balance=Money(row.credit_balance),
        )

    async def add(self, account: Account) -> None:
        await self._add(account)

    async def save(self, account: Account) -> None:
        await self._save(account)

    async def get(self, party_id: str) -> Account | None:
        """Resolves an applicant id or a linked matric number alike.

        Two lookups rather than an ``OR``, and the order matters only for cost: the party id is
        the primary key, so the common case is one index hit and no second query.
        """
        held = await self._get(party_id)
        if held is not None:
            return held
        return await self._find_one(t.accounts.c.student_id == party_id)

    async def all_active(self) -> tuple[Account, ...]:
        """Every account, in the order opened — which is what "active" means today.

        The port is explicit that nothing in the MVP closes an account, "because when an
        account stops being billable (graduation, withdrawal) is an institutional fact nobody
        has stated". When that rule arrives it lands as a predicate here, and the batch does
        not change.
        """
        return await self._list()


class PostgresFeeScheduleRepository(PostgresRepository[FeeSchedule], FeeScheduleRepositoryPort):
    """Holds published fee schedules in Postgres, keyed by session."""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(engine, label="fee schedule", table=t.fee_schedules, key=("session_id",))

    @property
    def child_tables(self) -> Sequence[tuple[Table, Sequence[str]]]:
        return ((t.session_fee_lines, ("session_id",)),)

    def identity_of(self, aggregate: FeeSchedule) -> tuple[str]:
        return (aggregate.session_id,)

    def row_of(self, aggregate: FeeSchedule) -> dict[str, Any]:
        return {
            "session_id": aggregate.session_id,
            "acceptance_fee": aggregate.acceptance_fee.amount,
            "matriculation_fee": aggregate.matriculation_fee.amount,
        }

    def child_rows_of(self, aggregate: FeeSchedule) -> Mapping[Table, Sequence[dict[str, Any]]]:
        return {
            t.session_fee_lines: [
                {
                    "session_id": aggregate.session_id,
                    "program_id": line.program_id,
                    "level": line.level.value,
                    "amount": line.amount.amount,
                }
                for line in aggregate.session_fee_lines
            ]
        }

    def restore(self, row: Row[Any], children: Mapping[Table, Sequence[Row[Any]]]) -> FeeSchedule:
        return FeeSchedule.for_session(
            row.session_id,
            acceptance_fee=Money(row.acceptance_fee),
            matriculation_fee=Money(row.matriculation_fee),
            session_fees=[
                SessionFeeLine(
                    program_id=line.program_id,
                    level=Level(line.level),
                    amount=Money(line.amount),
                )
                for line in children.get(t.session_fee_lines, ())
            ],
        )

    async def add(self, schedule: FeeSchedule) -> None:
        await self._add(schedule)

    async def save(self, schedule: FeeSchedule) -> None:
        await self._save(schedule)

    async def get(self, session_id: str) -> FeeSchedule | None:
        return await self._get(session_id)


class PostgresPaymentIntentRepository(
    PostgresRepository[PaymentIntent], PaymentIntentRepositoryPort
):
    """Holds payment intents in Postgres, keyed by the gateway's own reference."""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(
            engine, label="payment intent", table=t.payment_intents, key=("reference",)
        )

    def identity_of(self, aggregate: PaymentIntent) -> tuple[str]:
        return (aggregate.reference,)

    def row_of(self, aggregate: PaymentIntent) -> dict[str, Any]:
        return {
            "reference": aggregate.reference,
            "party_id": aggregate.party_id,
            "amount": aggregate.amount.amount,
            "confirmed_amount": (
                None if aggregate.confirmed_amount is None else aggregate.confirmed_amount.amount
            ),
            "initiated_at": aggregate.initiated_at,
            "resolved_at": aggregate.resolved_at,
            "ttl_seconds": int(aggregate.ttl.total_seconds()),
            "status": aggregate.status.value,
            "failure_reason": aggregate.failure_reason,
        }

    def restore(self, row: Row[Any], children: Mapping[Table, Sequence[Row[Any]]]) -> PaymentIntent:
        return PaymentIntent.restore(
            row.reference,
            row.party_id,
            Money(row.amount),
            row.initiated_at,
            timedelta(seconds=row.ttl_seconds),
            status=PaymentIntentStatus(row.status),
            confirmed_amount=(
                None if row.confirmed_amount is None else Money(row.confirmed_amount)
            ),
            resolved_at=row.resolved_at,
            failure_reason=row.failure_reason,
        )

    async def add(self, intent: PaymentIntent) -> None:
        await self._add(intent)

    async def save(self, intent: PaymentIntent) -> None:
        await self._save(intent)

    async def get(self, reference: str) -> PaymentIntent | None:
        return await self._get(reference)

    async def all_initiated(self) -> tuple[PaymentIntent, ...]:
        """Every intent the gateway has said nothing about, in the order opened.

        Deliberately not "every stale intent". The port refuses a ``datetime`` in its signature
        — "the TTL is applied by ``ReconcilePaymentIntents`` against the instant it was handed,
        and pushing it into a ``WHERE`` clause would put a piece of this context's judgement in
        the one layer that is meant to be swappable". So the filter here is the status, which is
        a fact, and the staleness is decided by the caller.
        """
        return await self._list(t.payment_intents.c.status == PaymentIntentStatus.INITIATED.value)
