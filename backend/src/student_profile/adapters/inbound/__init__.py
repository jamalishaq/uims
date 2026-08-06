"""Student Profile inbound adapters — the ways the outside world reaches the use case.

Two now, and they meet at the same use case. The handler for Admissions'
``StudentMatriculated`` creates the student a matriculated applicant became; the HTTP router
in ``http/`` registers one by hand. Both call ``RegisterNewStudent``, so the matric number is
composed by the same issuer from the same sequence either way — which is the whole reason
CLAUDE.md section 3 insists both creation paths go through one issuer.

The router is not re-exported here: it is mounted by the composition root through the module,
not imported as an object.
"""

from student_profile.adapters.inbound.student_matriculated_handler import (
    STUDENT_MATRICULATED,
    StudentMatriculatedHandler,
    StudentMatriculatedMessage,
)

__all__ = [
    "STUDENT_MATRICULATED",
    "StudentMatriculatedHandler",
    "StudentMatriculatedMessage",
]
