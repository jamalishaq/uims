"""HTTP routes for Academic Records: read a record, and correct a grade.

``adapters/inbound/__init__.py`` predicted this file too — "when one arrives it calls
``CorrectGrade`` and ``ReadAcademicRecord``, and the correction stays a human act rather than
something a publisher can trigger" — and those are exactly the two routes.

**There is deliberately no route that records a grade.** Recording is driven by
``GradeSubmitted`` arriving on the bus from Faculty & Department, and an HTTP endpoint doing it
would be a second way into a transcript that bypasses the lecturer-assignment check the
publishing context performs. Correction is the exception, and it demands a reason and an
authoriser precisely because it is the one path that can change a mark already recorded.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from academic_records.adapters.inbound.http.schemas import (
    AcademicRecordResponse,
    CorrectGradeRequest,
    GradeCorrectedResponse,
)
from academic_records.application.correct_grade import CorrectGrade, CorrectGradeCommand
from academic_records.application.read_academic_record import ReadAcademicRecord
from academic_records.application.views import AcademicRecordView, GradeCorrectedView
from http_api import dependencies_of, error_responses

STATE_KEY = "academic_records"
"""Where this context's use cases hang on ``app.state``. Owned here, read by the root."""


class AcademicRecordsDependencies:
    """The use cases this router needs, wired once at startup."""

    def __init__(
        self,
        read_academic_record: ReadAcademicRecord,
        correct_grade: CorrectGrade,
    ) -> None:
        self.read_academic_record = read_academic_record
        self.correct_grade = correct_grade


def _deps(request: Request) -> AcademicRecordsDependencies:
    return dependencies_of(request, STATE_KEY, AcademicRecordsDependencies)


Deps = Annotated[AcademicRecordsDependencies, Depends(_deps)]

router = APIRouter(prefix="/academic-records", tags=["academic-records"])


@router.get(
    "/records/{student_id}",
    response_model=AcademicRecordResponse,
    summary="Read a student's academic record",
    responses=error_responses(404, 422, 500, 503),
)
async def read_academic_record(student_id: str, deps: Deps) -> AcademicRecordResponse:
    """The whole transcript, its GPAs, its CGPA and the standing that follows from it.

    ``execute`` rather than ``find``: over HTTP, a student with no record is a 404, and the
    ``None``-returning variant exists for the cross-context adapter that needs the absence as
    a value rather than as a status.
    """
    record = await deps.read_academic_record.execute(student_id)
    return AcademicRecordResponse.of(AcademicRecordView.of(record))


@router.post(
    "/records/{student_id}/corrections",
    status_code=status.HTTP_201_CREATED,
    response_model=GradeCorrectedResponse,
    summary="Correct a recorded grade",
    responses=error_responses(404, 409, 422, 500, 503),
)
async def correct_grade(
    student_id: str, body: CorrectGradeRequest, deps: Deps
) -> GradeCorrectedResponse:
    """Change a mark already recorded, leaving an audit entry behind.

    The only route in this context that can alter a transcript. It appends rather than
    overwrites: the previous score, the reason and the authoriser stay on the record.
    """
    corrected = await deps.correct_grade.execute(
        CorrectGradeCommand(student_id=student_id, **body.model_dump())
    )
    return GradeCorrectedResponse.of(GradeCorrectedView.of(corrected))


__all__ = ["STATE_KEY", "AcademicRecordsDependencies", "router"]
