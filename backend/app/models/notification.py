import enum

from sqlalchemy import String, Text, Boolean, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin


class NotificationAudience(str, enum.Enum):
    ALL = "all"
    FACULTY = "faculty"
    DEPARTMENT = "department"
    PROGRAM = "program"
    STUDENT = "student"


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    audience: Mapped[NotificationAudience] = mapped_column(Enum(NotificationAudience))
    audience_id: Mapped[int | None] = mapped_column(nullable=True)  # FK to faculty/dept/program depending on audience
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
