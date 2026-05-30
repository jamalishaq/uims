from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role

router = APIRouter()


@router.get("")
async def list_hostels(db: AsyncSession = Depends(get_db)):
    pass


@router.post("/apply")
async def apply_for_accommodation(db: AsyncSession = Depends(get_db), user=Depends(require_role("student"))):
    pass


@router.post("/allocate")
async def allocate_room(db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin", "registrar"))):
    pass
