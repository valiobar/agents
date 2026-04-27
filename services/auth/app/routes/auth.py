from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from jose import JWTError

from app.models.user import (
    UserCreate,
    UserLogin,
    RefreshRequest,
    GoogleOAuthRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService
from app.repositories.user_repo import UserRepository
from app.utils.jwt import decode_token
from app.utils.db import get_database


router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service() -> AuthService:
    db = get_database()
    user_repo = UserRepository(db)
    return AuthService(user_repo)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, auth_service: AuthServiceDep):
    return await auth_service.register(data)


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, auth_service: AuthServiceDep):
    return await auth_service.login(data)


@router.post("/oauth/google", response_model=TokenResponse)
async def oauth_google(data: GoogleOAuthRequest, auth_service: AuthServiceDep):
    return await auth_service.oauth_google(data)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, auth_service: AuthServiceDep):
    return await auth_service.refresh(data)


@router.get("/me", response_model=UserResponse)
async def me(
    auth_service: AuthServiceDep,
    authorization: Annotated[str, Header()],
):
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return await auth_service.get_current_user(payload["sub"])
