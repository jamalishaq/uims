"""The ``Faculty`` aggregate: the top level of the university's academic structure."""

from faculty_department.domain.values import require_code, require_identifier, require_text


class Faculty:
    """A faculty, e.g. the Faculty of Science. Departments reference it by id."""

    def __init__(self, faculty_id: str, name: str, code: str) -> None:
        self._faculty_id = require_identifier(faculty_id, "faculty_id")
        self._name = require_text(name, "faculty name")
        self._code = require_code(code, "faculty code")

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
        self._name = require_text(name, "faculty name")

    def __repr__(self) -> str:
        return f"Faculty(faculty_id={self._faculty_id!r}, code={self._code!r})"
