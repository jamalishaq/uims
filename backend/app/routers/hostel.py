from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.hostel import Hostel, Room, Allocation, RoomType
from app.models.student import Student
from app.models.user import User
from app.schemas.hostel import ApplyRequest, AllocateRequest, AllocationOut, HostelOut, RoomOut

router = APIRouter()


@router.get("", response_model=list[HostelOut])
async def list_hostels(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Hostel))
    hostels = result.scalars().all()
    return hostels


@router.get("/rooms", response_model=list[RoomOut])
async def list_rooms(
    hostel_id: int | None = Query(None, description="Filter by hostel"),
    room_type: RoomType | None = Query(None, description="Filter by room type"),
    available_only: bool = Query(True, description="Return only available rooms"),
    db: AsyncSession = Depends(get_db),
):
    query = select(Room).options(selectinload(Room.hostel))
    if hostel_id is not None:
        query = query.where(Room.hostel_id == hostel_id)
    if room_type is not None:
        query = query.where(Room.room_type == room_type)
    if available_only:
        query = query.where(Room.is_available == True)

    result = await db.execute(query)
    rooms = result.scalars().all()

    return [
        RoomOut(
            id=r.id,
            hostel_id=r.hostel_id,
            room_number=r.room_number,
            room_type=r.room_type,
            capacity=r.capacity,
            is_available=r.is_available,
            hostel_name=r.hostel.name if r.hostel else None,
        )
        for r in rooms
    ]


@router.post("/apply", status_code=status.HTTP_201_CREATED, response_model=AllocationOut)
async def apply_for_accommodation(
    body: ApplyRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student")),
):
    # Resolve student record for the logged-in user
    result = await db.execute(select(Student).where(Student.user_id == user.id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found")

    # Prevent duplicate active allocation for the same semester
    existing = await db.execute(
        select(Allocation).where(
            Allocation.student_id == student.id,
            Allocation.semester_id == body.semester_id,
            Allocation.is_active == True,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active accommodation allocation already exists for this semester",
        )

    # Find a suitable available room
    room_query = select(Room).where(Room.is_available == True)
    if body.preferred_room_type:
        room_query = room_query.where(Room.room_type == body.preferred_room_type)
    room_query = room_query.limit(1)

    room_result = await db.execute(room_query)
    room = room_result.scalar_one_or_none()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No available rooms matching the requested type",
        )

    # Create allocation and mark room unavailable
    allocation = Allocation(
        student_id=student.id,
        room_id=room.id,
        semester_id=body.semester_id,
        is_active=True,
    )
    room.is_available = False
    db.add(allocation)
    await db.commit()
    await db.refresh(allocation)

    return allocation


@router.post("/allocate", status_code=status.HTTP_201_CREATED, response_model=AllocationOut)
async def allocate_room(
    body: AllocateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("super_admin", "registrar")),
):
    # Validate student exists
    student = await db.get(Student, body.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Validate room exists and is available
    room = await db.get(Room, body.room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if not room.is_available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Room is not available",
        )

    # Prevent duplicate active allocation for the same student/semester
    existing = await db.execute(
        select(Allocation).where(
            Allocation.student_id == body.student_id,
            Allocation.semester_id == body.semester_id,
            Allocation.is_active == True,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student already has an active allocation for this semester",
        )

    allocation = Allocation(
        student_id=body.student_id,
        room_id=body.room_id,
        semester_id=body.semester_id,
        is_active=True,
    )
    room.is_available = False
    db.add(allocation)
    await db.commit()
    await db.refresh(allocation)

    return allocation


@router.delete("/allocate/{allocation_id}", response_model=dict)
async def revoke_allocation(
    allocation_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("super_admin", "registrar")),
):
    allocation = await db.get(Allocation, allocation_id)
    if not allocation or not allocation.is_active:
        raise HTTPException(status_code=404, detail="Active allocation not found")

    # Free the room
    room = await db.get(Room, allocation.room_id)
    if room:
        room.is_available = True

    allocation.is_active = False
    await db.commit()

    return {"message": "Allocation revoked successfully"}


@router.get("/my-allocation", response_model=AllocationOut | None)
async def my_allocation(
    semester_id: int = Query(..., description="Semester to check"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("student")),
):
    result = await db.execute(select(Student).where(Student.user_id == user.id))
    student = result.scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found")

    alloc_result = await db.execute(
        select(Allocation).where(
            Allocation.student_id == student.id,
            Allocation.semester_id == semester_id,
            Allocation.is_active == True,
        )
    )
    return alloc_result.scalar_one_or_none()
