from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role

router = APIRouter()


@router.get("")
async def list_staff(db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin", "registrar"))):
    # TODO: paginated list with filters (department, staff_type)
    pass


@router.post("")
async def create_staff(db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin"))):
    # TODO: create user + staff record
    pass
