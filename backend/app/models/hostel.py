import enum

from sqlalchemy import String, Integer, Boolean, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class RoomType(str, enum.Enum):
    SINGLE = "single"
    DOUBLE = "double"
    QUAD = "quad"


class Hostel(TimestampMixin, Base):
    __tablename__ = "hostels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    gender: Mapped[str] = mapped_column(String(10))  # male / female / mixed

    rooms: Mapped[list["Room"]] = relationship(back_populates="hostel")


class Room(TimestampMixin, Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    hostel_id: Mapped[int] = mapped_column(ForeignKey("hostels.id"))
    room_number: Mapped[str] = mapped_column(String(20))
    room_type: Mapped[RoomType] = mapped_column(Enum(RoomType))
    capacity: Mapped[int] = mapped_column(Integer)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)

    hostel: Mapped[Hostel] = relationship(back_populates="rooms")


class Allocation(TimestampMixin, Base):
    __tablename__ = "allocations"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
