from fastapi import HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from jose import JWTError

from app.repositories.user_repo import UserRepository
from app.utils.security import hash_password, verify_password
from app.utils.jwt import create_access_token, create_refresh_token, decode_token
from app.config import settings
from app.models.user import (
    UserCreate,
    UserLogin,
    RefreshRequest,
    GoogleOAuthRequest,
    TokenResponse,
    UserResponse,
)


class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def register(self, data: UserCreate) -> TokenResponse:
        existing = await self.user_repo.find_by_email(data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        user = await self.user_repo.create(
            {
                "email": data.email,
                "password_hash": hash_password(data.password),
                "name": data.name,
                "auth_provider": "credentials",
            }
        )
        return self._issue_tokens(user.id)

    async def login(self, data: UserLogin) -> TokenResponse:
        user = await self.user_repo.find_by_email(data.email)
        if not user or not user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        if not verify_password(data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        return self._issue_tokens(user.id)

    async def oauth_google(self, data: GoogleOAuthRequest) -> TokenResponse:
        try:
            idinfo = google_id_token.verify_oauth2_token(
                data.id_token,
                google_requests.Request(),
                settings.google_client_id,
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google ID token",
            )

        google_id = idinfo["sub"]
        email = idinfo["email"]
        name = idinfo.get("name", email.split("@")[0])
        image = idinfo.get("picture")

        user = await self.user_repo.find_by_google_id(google_id)
        if user:
            return self._issue_tokens(user.id)

        existing = await self.user_repo.find_by_email(email)
        if existing:
            await self.user_repo.update_auth_provider(
                existing.id, "both", google_id
            )
            return self._issue_tokens(existing.id)

        user = await self.user_repo.create(
            {
                "email": email,
                "name": name,
                "image": image,
                "google_id": google_id,
                "auth_provider": "google",
            }
        )
        return self._issue_tokens(user.id)

    async def refresh(self, data: RefreshRequest) -> TokenResponse:
        try:
            payload = decode_token(data.refresh_token)
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is not a refresh token",
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        user = await self.user_repo.find_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        return self._issue_tokens(user.id)

    async def get_current_user(self, user_id: str) -> UserResponse:
        user = await self.user_repo.find_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            image=user.image,
            auth_provider=user.auth_provider,
        )

    def _issue_tokens(self, user_id: str) -> TokenResponse:
        return TokenResponse(
            access_token=create_access_token(user_id),
            refresh_token=create_refresh_token(user_id),
        )
