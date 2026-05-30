from __future__ import annotations
from datetime import date
from pydantic import BaseModel


class BookOut(BaseModel):
    id: int
    title: str
    author: str
    isbn: str | None = None
    total_copies: int
    available_copies: int
    model_config = {"from_attributes": True}


class BorrowRequest(BaseModel):
    book_id: int


class BorrowingOut(BaseModel):
    id: int
    book_id: int
    student_id: int
    borrowed_date: date
    due_date: date
    returned_date: date | None = None
    fine: float
    is_returned: bool
    model_config = {"from_attributes": True}
