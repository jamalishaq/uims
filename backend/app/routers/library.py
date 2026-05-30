from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.library import Book, Borrowing
from app.models.student import Student
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.library import BookOut, BorrowingOut, BorrowRequest

router = APIRouter()

FINE_PER_DAY = 50.0  # naira


@router.get("/books", response_model=list[BookOut])
async def search_books(
    q: str | None = Query(default=None, description="Search by title or author"),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Book)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                Book.title.ilike(pattern),
                Book.author.ilike(pattern),
            )
        )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/borrow", response_model=BorrowingOut)
async def borrow_book(
    body: BorrowRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student")),
):
    # Resolve student record from the authenticated user
    result = await db.execute(select(Student).where(Student.user_id == user.id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found")

    # Fetch the requested book
    book = await db.get(Book, body.book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if book.available_copies < 1:
        raise HTTPException(status_code=409, detail="No copies available")

    # Check the student doesn't already have an active borrowing of this book
    active_check = await db.execute(
        select(Borrowing).where(
            Borrowing.book_id == body.book_id,
            Borrowing.student_id == student.id,
            Borrowing.is_returned == False,
        )
    )
    if active_check.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="You already have this book borrowed")

    today = date.today()
    borrowing = Borrowing(
        book_id=book.id,
        student_id=student.id,
        borrowed_date=today,
        due_date=today + timedelta(days=14),
        fine=0.0,
        is_returned=False,
    )
    book.available_copies -= 1

    db.add(borrowing)
    await db.commit()
    await db.refresh(borrowing)
    return borrowing


@router.post("/return/{borrowing_id}", response_model=BorrowingOut)
async def return_book(
    borrowing_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student", "librarian")),
):
    borrowing = await db.get(Borrowing, borrowing_id)
    if not borrowing:
        raise HTTPException(status_code=404, detail="Borrowing record not found")
    if borrowing.is_returned:
        raise HTTPException(status_code=409, detail="Book already returned")

    # Students may only return their own borrowings
    if user.role == "student":
        result = await db.execute(select(Student).where(Student.user_id == user.id))
        student = result.scalar_one_or_none()
        if not student or borrowing.student_id != student.id:
            raise HTTPException(status_code=403, detail="Access denied")

    today = date.today()
    overdue_days = max(0, (today - borrowing.due_date).days)
    fine = overdue_days * FINE_PER_DAY

    borrowing.returned_date = today
    borrowing.fine = fine
    borrowing.is_returned = True

    book = await db.get(Book, borrowing.book_id)
    if book:
        book.available_copies += 1

    await db.commit()
    await db.refresh(borrowing)
    return borrowing
