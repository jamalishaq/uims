"""The ``Program`` aggregate: a course of study offered by a department.

``is_admitting`` is the fact Admissions checks at application time. Nothing else
about a program — duration, award, level — is modelled here: those are
institutional facts, not inferable.
"""

from faculty_department.domain.values import require_code, require_identifier, require_text


class Program:
    """A degree program, e.g. B.Sc. Computer Science."""

    def __init__(
        self,
        program_id: str,
        department_id: str,
        name: str,
        code: str,
        *,
        admitting: bool = False,
    ) -> None:
        self._program_id = require_identifier(program_id, "program_id")
        self._department_id = require_identifier(department_id, "department_id")
        self._name = require_text(name, "program name")
        self._code = require_code(code, "program code")
        self._admitting = bool(admitting)

    @classmethod
    def create(cls, program_id: str, department_id: str, name: str, code: str) -> "Program":
        """A new program is not admitting until someone opens it deliberately."""
        return cls(program_id, department_id, name, code, admitting=False)

    @property
    def program_id(self) -> str:
        return self._program_id

    @property
    def department_id(self) -> str:
        return self._department_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def code(self) -> str:
        return self._code

    @property
    def is_admitting(self) -> bool:
        return self._admitting

    def open_admissions(self) -> None:
        self._admitting = True

    def close_admissions(self) -> None:
        self._admitting = False

    def rename(self, name: str) -> None:
        self._name = require_text(name, "program name")

    def __repr__(self) -> str:
        return (
            f"Program(program_id={self._program_id!r}, code={self._code!r}, "
            f"admitting={self._admitting})"
        )
