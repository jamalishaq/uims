from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role

router = APIRouter()


@router.post("")
async def register_thesis(db: AsyncSession = Depends(get_db), user=Depends(require_role("student"))):
    pass


@router.post("/{thesis_id}/submit")
async def submit_thesis(thesis_id: int, db: AsyncSession = Depends(get_db), user=Depends(require_role("student"))):
    # TODO: upload file to S3
    pass


@router.post("/{thesis_id}/review")
async def review_thesis(thesis_id: int, db: AsyncSession = Depends(get_db), user=Depends(require_role("lecturer"))):
    pass
