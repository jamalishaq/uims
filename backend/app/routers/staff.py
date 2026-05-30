from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.dependencies import require_role
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.models.staff import Staff
from app.schemas.staff import StaffCreateRequest, StaffResponse

router = APIRouter()


@router.get("", response_model=list[StaffResponse])
async def list_staff(
    department_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("hod", "dean", "registrar", "super_admin")),
):
    query = select(Staff)
    if department_id is not None:
        query = query.where(Staff.department_id == department_id)
    result = await db.execute(query)
    staff_list = result.scalars().all()
    return staff_list


@router.post("", response_model=StaffResponse, status_code=status.HTTP_201_CREATED)
async def create_staff(
    body: StaffCreateRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_role("super_admin", "registrar")),
):
    # Check that email is not already taken
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    username = f"{body.first_name.lower()}.{body.last_name.lower()}"

    # Ensure username uniqueness
    result = await db.execute(select(User).where(User.username == username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already taken")

    # Generate a temporary password (first_name + last_name all lowercase)
    temp_password = f"{body.first_name.lower()}{body.last_name.lower()}"

    new_user = User(
        email=body.email,
        username=username,
        password_hash=hash_password(temp_password),
        role=UserRole.LECTURER,
        is_active=True,
    )
    db.add(new_user)
    await db.flush()  # get new_user.id without committing

    new_staff = Staff(
        user_id=new_user.id,
        department_id=body.department_id,
        staff_type=body.staff_type,
        rank=body.rank,
        designation=body.designation,
        phone=body.phone,
    )
    db.add(new_staff)
    await db.commit()
    await db.refresh(new_staff)

    # Eagerly load the user relationship for the response
    await db.refresh(new_staff, attribute_names=["user"])
    return new_staff
