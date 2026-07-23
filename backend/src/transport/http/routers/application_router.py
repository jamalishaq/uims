from uuid import UUID
from fastapi import APIRouter, Depends, status, Query

from src.service import ApplicationService
from src.domain.models import ScreeningStatus
from src.transport.http.dependencies import get_application_service
from src.transport.http.schemas import (
    ApplicationCreateRequest,
    ApplicationEditRequest,
    ApplicationRejectRequest,
    ApplicationResponse
)

application_router = APIRouter(prefix="/api/v1/applications", tags=["Applications"])


@application_router.post(
    "/apply", 
    status_code=status.HTTP_201_CREATED, 
    response_model=ApplicationResponse
)
async def apply(
    payload: ApplicationCreateRequest, 
    service: ApplicationService = Depends(get_application_service)
):
    return await service.submitApplication(
        applicant_details=payload.applicant_details,
        jamb_details=payload.jamb_details,
        olevel_grades=payload.olevel_grades,
        indigine_claim=payload.is_indegene,
        program_id=payload.program_id
    )


@application_router.patch(
    "/{application_id}/reject", 
    response_model=ApplicationResponse
)
async def reject(
    application_id: UUID, 
    payload: ApplicationRejectRequest,
    service: ApplicationService = Depends(get_application_service)
):
    reason = payload.rejection_reason if payload else None
    return await service.reject_application(application_id, reason=reason)


@application_router.patch(
    "/{application_id}/admit", 
    response_model=ApplicationResponse
)
async def admit(
    application_id: UUID, 
    service: ApplicationService = Depends(get_application_service)
):
    return await service.accept_application(application_id)


@application_router.patch(
    "/{application_id}/confirm", 
    response_model=ApplicationResponse
)
async def confirm(
    application_id: UUID, 
    service: ApplicationService = Depends(get_application_service)
):
    return await service.confrim_application(application_id)


@application_router.patch(
    "/{application_id}/waitlist", 
    response_model=ApplicationResponse
)
async def waitlist(
    application_id: UUID, 
    service: ApplicationService = Depends(get_application_service)
):
    return await service.waitlist_application(application_id)


@application_router.patch(
    "/{application_id}/edit", 
    response_model=ApplicationResponse
)
async def edit(
    application_id: UUID, 
    payload: ApplicationEditRequest, 
    service: ApplicationService = Depends(get_application_service)
):
    return await service.edit_application(application_id=application_id, changes=payload)


@application_router.get(
    "/", 
    response_model=list[ApplicationResponse]
)
async def list_applications(
    program_id: str, 
    screening_status: ScreeningStatus | None = Query(default=None),
    is_indegene: bool | None = Query(default=None),
    service: ApplicationService = Depends(get_application_service)
):
    return await service.list_applications(program_id, screening_status, is_indegene)
