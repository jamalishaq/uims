from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime

from app.core.database import get_db
from app.core.dependencies import require_role, get_current_user
from app.core.security import hash_password
from app.models.admission import Application, ApplicationStatus
from app.models.user import User, UserRole
from app.models.student import Student, StudentStatus
from app.models.academic import Program
from app.schemas.admission import ApplicationCreate, ApplicationOut, DecisionRequest
from app.schemas.common import MessageResponse

router = APIRouter()


@router.post("/apply", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
async def submit_application(
    body: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("applicant")),
):
    # Check for existing active application for the same program+session
    existing_result = await db.execute(
        select(Application).where(
            Application.user_id == user.id,
            Application.program_id == body.program_id,
            Application.session_id == body.session_id,
            Application.status != ApplicationStatus.REJECTED,
        )
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application already submitted",
        )

    application = Application(
        user_id=user.id,
        program_id=body.program_id,
        session_id=body.session_id,
        status=ApplicationStatus.SUBMITTED,
        first_name=body.first_name,
        last_name=body.last_name,
        phone=body.phone,
        address=body.address,
        date_of_birth=body.date_of_birth,
    )
    db.add(application)
    await db.commit()
    await db.refresh(application)
    return application


@router.get("/applications", response_model=list[ApplicationOut])
async def list_applications(
    app_status: ApplicationStatus | None = Query(None),
    program_id: int | None = Query(None),
    session_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("super_admin", "registrar")),
):
    query = select(Application)

    if app_status is not None:
        query = query.where(Application.status == app_status)
    if program_id is not None:
        query = query.where(Application.program_id == program_id)
    if session_id is not None:
        query = query.where(Application.session_id == session_id)

    query = query.order_by(Application.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/applications/{application_id}/decision", response_model=MessageResponse)
async def make_decision(
    application_id: int,
    body: DecisionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("super_admin", "registrar")),
):
    application = await db.get(Application, application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    if body.action not in ("accept", "reject"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Action must be 'accept' or 'reject'",
        )

    if body.action == "accept":
        application.status = ApplicationStatus.ACCEPTED
    else:
        application.status = ApplicationStatus.REJECTED
        application.rejection_reason = body.rejection_reason

    await db.commit()
    return MessageResponse(message=f"Application {body.action}ed successfully")


@router.post("/applications/{application_id}/enroll")
async def enroll_accepted_applicant(
    application_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("super_admin", "registrar")),
):
    # 1. Fetch application; 404 if not found
    application = await db.get(Application, application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found",
        )

    # 2. Ensure application is accepted
    if application.status != ApplicationStatus.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application must be accepted before enrollment",
        )

    # 3. Fetch the Program for its code
    program = await db.get(Program, application.program_id)
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program not found",
        )

    # 4. Generate matric number
    count_result = await db.execute(
        select(func.count()).where(Student.program_id == application.program_id)
    )
    seq = (count_result.scalar() or 0) + 1
    matric_number = f"{program.code.upper()}-{datetime.now().year}-{seq:04d}"

    # 5. Promote the applicant's existing User to student role
    applicant_user = await db.get(User, application.user_id)
    if not applicant_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Applicant user not found",
        )

    applicant_user.role = UserRole.STUDENT
    applicant_user.username = matric_number
    await db.flush()

    # 6. Create Student record linked to the promoted user
    student = Student(
        user_id=applicant_user.id,
        matric_number=matric_number,
        program_id=application.program_id,
        level=100,
        status=StudentStatus.ACTIVE,
    )
    db.add(student)
    await db.flush()

    # 7. Mark application as enrolled
    application.status = ApplicationStatus.ENROLLED

    # 8. Commit everything
    await db.commit()
    await db.refresh(student)

    # 9. Return matric number and student id
    return {
        "message": "Student enrolled successfully",
        "matric_number": matric_number,
        "student_id": student.id,
    }
