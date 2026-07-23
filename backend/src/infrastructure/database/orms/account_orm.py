from typing import TYPE_CHECKING
import enum
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy import String, Enum, DateTime, ForeignKey, Table, Column, func, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, PersonORM
if TYPE_CHECKING:
    from .audit_log import AuditLogORM

class Role(str, enum.Enum):
    STUDENT = "Student"
    FACULTY = "Faculty"
    REGISTRAR = "Registrar"
    FINANCE = "Finance"
    ADMIN = "Admin"

account_roles = Table(
    "account_roles",
    Base.metadata,
    Column("account_id", Uuid, ForeignKey("accounts.account_id", ondelete="CASCADE"), primary_key=True),
    Column("role", Enum(Role), primary_key=True)
)

class AccountORM(Base, TimestampMixin):
    __tablename__ = "accounts"
    account_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(100))
    password: Mapped[str] = mapped_column(String(100))
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("persons.person_id"), index=True)
    linked_entity: Mapped["PersonORM"] = relationship()
    roles: Mapped[list[Role]] = relationship(secondary=account_roles, lazy="selectin")
    # sso_identifier: Mapped[str] = mapped_column(String(20))
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    actions: Mapped[list["AuditLogORM"]] = relationship(cascade="all, delete-orphan", passive_deletes=True, back_populates="actor")
