from fastapi import APIRouter, status, Depends

from src.transport.http.schemas import (
    ApplicationCreateRequest, 
    LoginRequest, 
    RefreshTokenRequest, 
    SwitchRoleRequest, 
    LogoutAllRequest, 
    LogoutRequest, 
    AccountResponse, 
    TokenResponse
)
from src.service.services.account_service import AccountService
from src.transport.http.dependencies import get_account_service

account_router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

# --- Endpoints ---

@account_router.post("/", status_code=status.HTTP_201_CREATED, response_model=AccountResponse)
async def create_user_account(
    payload: ApplicationCreateRequest, 
    service: AccountService = Depends(get_account_service)
):
    return await service.create_account(account_details=payload)


@account_router.post("/login", status_code=status.HTTP_200_OK, response_model=TokenResponse)
async def login(
    payload: LoginRequest, 
    service: AccountService = Depends(get_account_service)
):
    return await service.login(email=payload.email, password=payload.password)


@account_router.post("/refresh", status_code=status.HTTP_200_OK, response_model=TokenResponse)
async def refresh(
    payload: RefreshTokenRequest, 
    service: AccountService = Depends(get_account_service)
):
    return await service.refresh_tokens(refresh_token=payload.refresh_token)


@account_router.post("/switch-role", status_code=status.HTTP_200_OK, response_model=TokenResponse)
async def switch_role(
    payload: SwitchRoleRequest, 
    service: AccountService = Depends(get_account_service)
):
    return await service.switch_role(
        account_id=payload.account_id, 
        role=payload.target_role, 
        current_refresh_token=payload.current_refresh_token
    )


@account_router.post("/logout", status_code=status.HTTP_200_OK, response_model=bool)
async def logout(
    payload: LogoutRequest, 
    service: AccountService = Depends(get_account_service)
):
    return await service.logout(refresh_token=payload.refresh_token)


@account_router.post("/logout-all-session", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all_session(
    payload: LogoutAllRequest, 
    service: AccountService = Depends(get_account_service)
):
    await service.logout_all_devices(account_id=payload.account_id)