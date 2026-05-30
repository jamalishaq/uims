from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.notification import Notification, NotificationAudience
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse
from app.schemas.notifications import NotificationCreate, NotificationOut
from app.websockets.manager import manager

router = APIRouter()

# Mapping from UserRole to the NotificationAudience values that are visible to that role.
# A notification is visible when:
#   audience = ALL          → everyone
#   audience = STUDENT      → students (and admins who can see everything)
#   audience = FACULTY      → dean, hod, lecturer
#   audience = DEPARTMENT   → hod, lecturer
#   audience = PROGRAM      → lecturer, student
_ROLE_AUDIENCES: dict[str, list[NotificationAudience]] = {
    UserRole.SUPER_ADMIN: list(NotificationAudience),
    UserRole.REGISTRAR:   [NotificationAudience.ALL],
    UserRole.BURSAR:      [NotificationAudience.ALL],
    UserRole.DEAN:        [NotificationAudience.ALL, NotificationAudience.FACULTY],
    UserRole.HOD:         [NotificationAudience.ALL, NotificationAudience.FACULTY, NotificationAudience.DEPARTMENT],
    UserRole.LECTURER:    [NotificationAudience.ALL, NotificationAudience.FACULTY, NotificationAudience.DEPARTMENT, NotificationAudience.PROGRAM],
    UserRole.STUDENT:     [NotificationAudience.ALL, NotificationAudience.STUDENT, NotificationAudience.PROGRAM],
    UserRole.APPLICANT:   [NotificationAudience.ALL],
    UserRole.LIBRARIAN:   [NotificationAudience.ALL],
    UserRole.ALUMNI:      [NotificationAudience.ALL],
}


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return active notifications relevant to the current user's role, newest first."""
    visible_audiences = _ROLE_AUDIENCES.get(user.role, [NotificationAudience.ALL])

    stmt = (
        select(Notification)
        .where(
            Notification.is_active == True,  # noqa: E712
            Notification.audience.in_(visible_audiences),
        )
        .order_by(Notification.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=NotificationOut, status_code=status.HTTP_201_CREATED)
async def create_notification(
    body: NotificationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("super_admin", "registrar", "dean", "hod")),
):
    """Create a new notification and broadcast it over WebSocket to all connected clients."""
    notification = Notification(
        created_by=user.id,
        title=body.title,
        body=body.body,
        audience=body.audience,
        audience_id=body.audience_id,
        is_pinned=body.is_pinned,
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    # Broadcast to every connected user's personal notification room.
    # Rooms follow the pattern "notifications:{user_id}" (see app/websockets/notifications.py).
    # We iterate all active rooms and push to those that match the prefix so that any
    # currently-connected user receives the event in real time.
    payload = {
        "type": "notification",
        "id": notification.id,
        "title": notification.title,
        "body": notification.body,
        "audience": notification.audience.value,
        "audience_id": notification.audience_id,
        "is_pinned": notification.is_pinned,
        "created_at": notification.created_at.isoformat(),
    }
    for room in list(manager._rooms.keys()):
        if room.startswith("notifications:"):
            await manager.broadcast(room, payload)

    return notification


@router.patch("/{notification_id}/read", response_model=MessageResponse)
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Mark a notification as read.

    NOTE: The Notification model does not have a per-user `is_read` field — it is a
    broadcast model with no read-receipt join table.  Returning a simple acknowledgement
    is intentional; adding a UserNotificationRead join table is out of scope for this
    implementation.
    """
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.is_active == True,  # noqa: E712
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    # No per-user is_read field exists on the model; acknowledge without persisting state.
    return MessageResponse(message="ok")
