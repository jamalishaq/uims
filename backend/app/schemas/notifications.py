from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.notification import NotificationAudience


class NotificationCreate(BaseModel):
    title: str
    body: str
    audience: NotificationAudience
    audience_id: int | None = None
    is_pinned: bool = False


class NotificationOut(BaseModel):
    id: int
    created_by: int
    title: str
    body: str
    audience: NotificationAudience
    audience_id: int | None
    is_pinned: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
