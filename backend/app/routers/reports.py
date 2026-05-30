from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_role

router = APIRouter()


@router.get("/enrollment-stats")
async def enrollment_stats(db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin", "registrar", "dean", "hod"))):
    pass


@router.get("/pass-fail-rates")
async def pass_fail_rates(db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin", "dean", "hod"))):
    pass


@router.get("/fee-collection")
async def fee_collection(db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin", "bursar"))):
    pass


@router.get("/cgpa-distribution")
async def cgpa_distribution(db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin", "dean", "hod", "registrar"))):
    pass
