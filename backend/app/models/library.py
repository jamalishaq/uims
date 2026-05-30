from datetime import date

from sqlalchemy import String, Integer, Boolean, Float, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Book(TimestampMixin, Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    author: Mapped[str] = mapped_column(String(200))
    isbn: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    total_copies: Mapped[int] = mapped_column(Integer, default=1)
    available_copies: Mapped[int] = mapped_column(Integer, default=1)


class Borrowing(TimestampMixin, Base):
    __tablename__ = "borrowings"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    borrowed_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    returned_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    fine: Mapped[float] = mapped_column(Float, default=0.0)
    is_returned: Mapped[bool] = mapped_column(Boolean, default=False)
