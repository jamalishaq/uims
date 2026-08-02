"""The ``Department`` aggregate.

A separate aggregate from ``Faculty`` rather than a child of it: departments are
loaded and changed independently, and ``code`` is the fact Student Profile's
matric-number issuer will read through its own query port.
"""

from faculty_department.domain.values import require_code, require_identifier, require_text


class Department:
    """A department within a faculty, e.g. Computer Science under Science."""

    def __init__(self, department_id: str, faculty_id: str, name: str, code: str) -> None:
        self._department_id = require_identifier(department_id, "department_id")
        self._faculty_id = require_identifier(faculty_id, "faculty_id")
        self._name = require_text(name, "department name")
        self._code = require_code(code, "department code")

    @property
    def department_id(self) -> str:
        return self._department_id

    @property
    def faculty_id(self) -> str:
        return self._faculty_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def code(self) -> str:
        return self._code

    def rename(self, name: str) -> None:
        self._name = require_text(name, "department name")

    def __repr__(self) -> str:
        return f"Department(department_id={self._department_id!r}, code={self._code!r})"
