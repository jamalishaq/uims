"""Student Profile domain layer.

Owns the student identity anchor and, with it, matric number issuance: the ``Student``
aggregate, the per-department/year ``MatricSequence`` counter, and the single
``MatricNumberIssuer`` both creation paths go through. Stdlib only: no persistence, no
ports, no HTTP reaches this package.
"""

from student_profile.domain.errors import (
    InvalidBioDataError,
    InvalidDepartmentCodeError,
    InvalidEntryYearError,
    InvalidLevelError,
    InvalidMatricNumberError,
    InvalidSequenceStateError,
    MissingIdentifierError,
    StudentProfileError,
)
from student_profile.domain.matric_number import MatricNumber, MatricNumberFormat
from student_profile.domain.matric_number_issuer import MatricNumberIssuer
from student_profile.domain.matric_sequence import MatricSequence, SequenceKey
from student_profile.domain.student import Student
from student_profile.domain.values import BioData, DepartmentCode, EntryYear, Level

__all__ = [
    "BioData",
    "DepartmentCode",
    "EntryYear",
    "InvalidBioDataError",
    "InvalidDepartmentCodeError",
    "InvalidEntryYearError",
    "InvalidLevelError",
    "InvalidMatricNumberError",
    "InvalidSequenceStateError",
    "Level",
    "MatricNumber",
    "MatricNumberFormat",
    "MatricNumberIssuer",
    "MatricSequence",
    "MissingIdentifierError",
    "SequenceKey",
    "Student",
    "StudentProfileError",
]
