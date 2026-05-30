from pydantic import BaseModel


class EnrollRequest(BaseModel):
    section_id: int
