from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role

router = APIRouter()


@router.get("/books")
async def search_books(db: AsyncSession = Depends(get_db)):
    # TODO: search by title, author, isbn
    pass


@router.post("/borrow")
async def borrow_book(db: AsyncSession = Depends(get_db), user=Depends(require_role("librarian"))):
    pass


@router.post("/return/{borrowing_id}")
async def return_book(borrowing_id: int, db: AsyncSession = Depends(get_db), user=Depends(require_role("librarian"))):
    # TODO: mark returned, compute fine if overdue
    pass
