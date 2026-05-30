from pydantic import BaseModel, Field


class SubmitGradeRequest(BaseModel):
    ca_score: float = Field(..., ge=0, le=40)
    exam_score: float = Field(..., ge=0, le=60)
