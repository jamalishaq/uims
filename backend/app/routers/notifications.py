from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role

router = APIRouter()


@router.post("")
async def create_notification(db: AsyncSession = Depends(get_db), user=Depends(require_role("super_admin", "registrar", "dean", "hod"))):
    # TODO: create Notification, broadcast via WebSocket manager to targeted audience
    pass


@router.get("")
async def list_notifications(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    # TODO: return notifications matching user's role / faculty / dept / program
    pass
