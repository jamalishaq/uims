"""Wiring for the Student Profile tests.

This module is the swap point, and Phase 6.1 is what it was waiting for. ``students`` and
``sequences`` now come from ``adapters``, which resolves to the in-memory classes or the
Postgres ones depending on ``UMS_TEST_BACKEND`` — see ``tests/conftest.py``. Adapter
construction still happens *only* here, and the repository fixture is still annotated with its
port type rather than the concrete class.

Two fixtures stay concrete on purpose. ``departments`` is the anti-corruption adapter standing
in for Faculty & Department and tests have to register placements on it, so it is not a
repository and does not swap. ``sequences`` is annotated concretely because some tests read
``all()``, which is not on the port — but it *does* swap, because both adapters answer it, and
the counter is the one place in this system where the Postgres adapter differs from the
in-memory one in kind rather than in detail.
"""

import pytest
from tests.conftest import Adapters

from student_profile.adapters.inbound import StudentMatriculatedHandler
from student_profile.adapters.outbound import (
    InMemoryDepartmentCodeAdapter,
    InMemoryMatricSequenceRepository,
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
def students(adapters: Adapters) -> StudentRepositoryPort:
    return adapters.students()


@pytest.fixture
def sequences(adapters: Adapters) -> InMemoryMatricSequenceRepository:
    """Concrete on purpose: some tests read ``all()``, which is not on the port.

    Both adapters answer it, so this still swaps with the backend — the annotation names the
    in-memory class because that is what a reader needs in order to find ``all()``.
    """
    return adapters.sequences()


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
