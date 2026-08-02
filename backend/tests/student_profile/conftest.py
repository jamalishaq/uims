"""Wiring for the Student Profile tests.

This module is the swap point. Phase 6 replaces the in-memory adapters with Postgres
ones, and the requirement is that the application test suite runs unchanged against both
— so adapter construction happens *only* here, and every fixture is annotated with its
port type rather than the concrete class. A test that names an adapter directly is a test
that would have to be rewritten later.

The two exceptions are annotated concretely on purpose: the department-code adapter,
because tests have to register placements on it, and the sequence repository, because
some tests read every counter it holds.
"""

import pytest

from student_profile.adapters.inbound import StudentMatriculatedHandler
from student_profile.adapters.outbound import (
    InMemoryDepartmentCodeAdapter,
    InMemoryMatricSequenceRepository,
    InMemoryStudentRepository,
)
from student_profile.application import RegisterNewStudent
from student_profile.domain import MatricNumberIssuer
from student_profile.ports import (
    DepartmentCodePort,
    MatricSequenceRepositoryPort,
    StudentRepositoryPort,
)

CSC_PROGRAM_ID = "prog-csc-bsc"
MCB_PROGRAM_ID = "prog-mcb-bsc"
SESSION_2026 = "sess-2026"
SESSION_2027 = "sess-2027"
CSC_CODE = "0591"
MCB_CODE = "0672"


@pytest.fixture
def students() -> StudentRepositoryPort:
    return InMemoryStudentRepository()


@pytest.fixture
def sequences() -> InMemoryMatricSequenceRepository:
    """Concrete on purpose: some tests read every counter that was started."""
    return InMemoryMatricSequenceRepository()


@pytest.fixture
def departments() -> InMemoryDepartmentCodeAdapter:
    """Faculty & Department, as far as this context can see it.

    Pre-loaded with two programs across two sessions, which is the smallest table that
    can show a sequence being per-department *and* per-year rather than global.
    """
    adapter = InMemoryDepartmentCodeAdapter()
    adapter.register(CSC_PROGRAM_ID, SESSION_2026, CSC_CODE, 2026)
    adapter.register(CSC_PROGRAM_ID, SESSION_2027, CSC_CODE, 2027)
    adapter.register(MCB_PROGRAM_ID, SESSION_2026, MCB_CODE, 2026)
    return adapter


@pytest.fixture
def issuer() -> MatricNumberIssuer:
    """One issuer, shared by both creation paths. That sharing is the phase's point."""
    return MatricNumberIssuer()


@pytest.fixture
def register_new_student(
    students: StudentRepositoryPort,
    sequences: MatricSequenceRepositoryPort,
    departments: DepartmentCodePort,
    issuer: MatricNumberIssuer,
) -> RegisterNewStudent:
    return RegisterNewStudent(
        students=students, sequences=sequences, departments=departments, issuer=issuer
    )


@pytest.fixture
def matriculation_handler(
    register_new_student: RegisterNewStudent, students: StudentRepositoryPort
) -> StudentMatriculatedHandler:
    """The event path, wired to the *same* use case and therefore the same issuer."""
    return StudentMatriculatedHandler(register_new_student=register_new_student, students=students)
