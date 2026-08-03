"""Admissions' four repository ports, against Postgres.

Three are keyed by ``(program_id, session_id)``, which the base carries natively — every key
here is a tuple. The fourth, ``Applicant``, is the only aggregate in this context whose state
a constructor cannot express, and ``Applicant.restore`` is what this file calls instead.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import Row, Table
from sqlalchemy.ext.asyncio import AsyncEngine

from admissions.adapters.outbound.postgres import _tables as t
from admissions.adapters.outbound.postgres._repository import PostgresRepository
from admissions.domain.admission_cycle import AdmissionCycle
from admissions.domain.alternative_program_policy import AlternativeProgramPolicy
from admissions.domain.applicant import Applicant, ApplicationStatus
from admissions.domain.entry_requirement import ProgramEntryRequirement, SubjectGroup
from admissions.domain.values import BioData, UtmeResult, UtmeSubjectScore
from admissions.ports.admission_cycle_repository import AdmissionCycleRepositoryPort
from admissions.ports.alternative_program_policy_repository import (
    AlternativeProgramPolicyRepositoryPort,
)
from admissions.ports.applicant_repository import ApplicantRepositoryPort
from admissions.ports.entry_requirement_repository import ProgramEntryRequirementRepositoryPort


class PostgresApplicantRepository(PostgresRepository[Applicant], ApplicantRepositoryPort):
    """Holds applications in Postgres, lifecycle and all."""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(engine, label="applicant", table=t.applicants, key=("applicant_id",))

    @property
    def child_tables(self) -> Sequence[tuple[Table, Sequence[str]]]:
        return ((t.utme_scores, ("applicant_id",)),)

    def identity_of(self, aggregate: Applicant) -> tuple[str]:
        return (aggregate.applicant_id,)

    def row_of(self, aggregate: Applicant) -> dict[str, Any]:
        return {
            "applicant_id": aggregate.applicant_id,
            "applied_program_id": aggregate.applied_program_id,
            "offered_program_id": aggregate.offered_program_id,
            "session_id": aggregate.session_id,
            "full_name": aggregate.bio_data.full_name,
            "date_of_birth": aggregate.bio_data.date_of_birth,
            "email": aggregate.bio_data.email,
            "phone_number": aggregate.bio_data.phone_number,
            "status": aggregate.status.value,
            "fee_cleared": aggregate.is_fee_cleared,
        }

    def child_rows_of(self, aggregate: Applicant) -> Mapping[Table, Sequence[dict[str, Any]]]:
        return {
            t.utme_scores: [
                {
                    "applicant_id": aggregate.applicant_id,
                    "subject": score.subject,
                    "position": position,
                    "score": score.score,
                }
                for position, score in enumerate(aggregate.utme_result.scores)
            ]
        }

    def restore(self, row: Row[Any], children: Mapping[Table, Sequence[Row[Any]]]) -> Applicant:
        scores = sorted(children.get(t.utme_scores, ()), key=lambda child: child.position)
        return Applicant.restore(
            row.applicant_id,
            row.applied_program_id,
            row.session_id,
            BioData(
                full_name=row.full_name,
                date_of_birth=row.date_of_birth,
                email=row.email,
                phone_number=row.phone_number,
            ),
            UtmeResult(
                tuple(
                    UtmeSubjectScore(subject=child.subject, score=child.score) for child in scores
                )
            ),
            status=ApplicationStatus(row.status),
            offered_program_id=row.offered_program_id,
            fee_cleared=row.fee_cleared,
        )

    async def add(self, applicant: Applicant) -> None:
        await self._add(applicant)

    async def save(self, applicant: Applicant) -> None:
        await self._save(applicant)

    async def get(self, applicant_id: str) -> Applicant | None:
        return await self._get(applicant_id)

    async def list_for_session(self, session_id: str) -> tuple[Applicant, ...]:
        return await self._list(t.applicants.c.session_id == session_id)


class PostgresAdmissionCycleRepository(
    PostgresRepository[AdmissionCycle], AdmissionCycleRepositoryPort
):
    """Holds admission cycles in Postgres, keyed by the pair a cycle actually is."""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(
            engine,
            label="admission cycle",
            table=t.admission_cycles,
            key=("program_id", "session_id"),
        )

    def identity_of(self, aggregate: AdmissionCycle) -> tuple[str, str]:
        return (aggregate.program_id, aggregate.session_id)

    def row_of(self, aggregate: AdmissionCycle) -> dict[str, Any]:
        return {
            "program_id": aggregate.program_id,
            "session_id": aggregate.session_id,
            "quota": aggregate.quota,
            "offers_made": aggregate.offers_made,
        }

    def restore(
        self, row: Row[Any], children: Mapping[Table, Sequence[Row[Any]]]
    ) -> AdmissionCycle:
        return AdmissionCycle(
            row.program_id, row.session_id, row.quota, offers_made=row.offers_made
        )

    async def add(self, cycle: AdmissionCycle) -> None:
        await self._add(cycle)

    async def save(self, cycle: AdmissionCycle) -> None:
        await self._save(cycle)

    async def get(self, program_id: str, session_id: str) -> AdmissionCycle | None:
        return await self._get(program_id, session_id)


class PostgresProgramEntryRequirementRepository(
    PostgresRepository[ProgramEntryRequirement], ProgramEntryRequirementRepositoryPort
):
    """Holds published entry requirements in Postgres."""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(
            engine,
            label="entry requirement",
            table=t.entry_requirements,
            key=("program_id", "session_id"),
        )

    @property
    def child_tables(self) -> Sequence[tuple[Table, Sequence[str]]]:
        return (
            (t.required_subjects, ("program_id", "session_id")),
            (t.subject_groups, ("program_id", "session_id")),
        )

    def identity_of(self, aggregate: ProgramEntryRequirement) -> tuple[str, str]:
        return (aggregate.program_id, aggregate.session_id)

    def row_of(self, aggregate: ProgramEntryRequirement) -> dict[str, Any]:
        return {"program_id": aggregate.program_id, "session_id": aggregate.session_id}

    def child_rows_of(
        self, aggregate: ProgramEntryRequirement
    ) -> Mapping[Table, Sequence[dict[str, Any]]]:
        key = {"program_id": aggregate.program_id, "session_id": aggregate.session_id}
        return {
            t.required_subjects: [
                {**key, "subject": subject} for subject in sorted(aggregate.required_subjects)
            ],
            t.subject_groups: [
                {**key, "group_position": position, "subject": subject}
                for position, group in enumerate(aggregate.one_of_groups)
                for subject in sorted(group.options)
            ],
        }

    def restore(
        self, row: Row[Any], children: Mapping[Table, Sequence[Row[Any]]]
    ) -> ProgramEntryRequirement:
        groups: dict[int, set[str]] = {}
        for child in children.get(t.subject_groups, ()):
            groups.setdefault(child.group_position, set()).add(child.subject)
        return ProgramEntryRequirement(
            row.program_id,
            row.session_id,
            required_subjects=[child.subject for child in children.get(t.required_subjects, ())],
            one_of_groups=[
                SubjectGroup(options=frozenset(groups[position])) for position in sorted(groups)
            ],
        )

    async def add(self, requirement: ProgramEntryRequirement) -> None:
        await self._add(requirement)

    async def save(self, requirement: ProgramEntryRequirement) -> None:
        await self._save(requirement)

    async def get(self, program_id: str, session_id: str) -> ProgramEntryRequirement | None:
        return await self._get(program_id, session_id)


class PostgresAlternativeProgramPolicyRepository(
    PostgresRepository[AlternativeProgramPolicy], AlternativeProgramPolicyRepositoryPort
):
    """Holds fallback chains in Postgres, in the order that *is* the policy."""

    def __init__(self, engine: AsyncEngine) -> None:
        super().__init__(
            engine,
            label="alternative program policy",
            table=t.alternative_policies,
            key=("program_id", "session_id"),
        )

    @property
    def child_tables(self) -> Sequence[tuple[Table, Sequence[str]]]:
        return ((t.alternative_programs, ("program_id", "session_id")),)

    def identity_of(self, aggregate: AlternativeProgramPolicy) -> tuple[str, str]:
        return (aggregate.program_id, aggregate.session_id)

    def row_of(self, aggregate: AlternativeProgramPolicy) -> dict[str, Any]:
        return {"program_id": aggregate.program_id, "session_id": aggregate.session_id}

    def child_rows_of(
        self, aggregate: AlternativeProgramPolicy
    ) -> Mapping[Table, Sequence[dict[str, Any]]]:
        return {
            t.alternative_programs: [
                {
                    "program_id": aggregate.program_id,
                    "session_id": aggregate.session_id,
                    "position": position,
                    "alternative_program_id": alternative,
                }
                for position, alternative in enumerate(aggregate.alternatives)
            ]
        }

    def restore(
        self, row: Row[Any], children: Mapping[Table, Sequence[Row[Any]]]
    ) -> AlternativeProgramPolicy:
        alternatives = sorted(
            children.get(t.alternative_programs, ()), key=lambda child: child.position
        )
        return AlternativeProgramPolicy(
            row.program_id,
            row.session_id,
            [child.alternative_program_id for child in alternatives],
        )

    async def add(self, policy: AlternativeProgramPolicy) -> None:
        await self._add(policy)

    async def save(self, policy: AlternativeProgramPolicy) -> None:
        await self._save(policy)

    async def get(self, program_id: str, session_id: str) -> AlternativeProgramPolicy | None:
        return await self._get(program_id, session_id)
