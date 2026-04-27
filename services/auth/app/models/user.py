from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1, max_length=100)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class GoogleOAuthRequest(BaseModel):
    id_token: str


class UserInDB(BaseModel):
    id: str = Field(alias="_id")
    email: str
    password_hash: Optional[str] = None
    name: str
    image: Optional[str] = None
    google_id: Optional[str] = None
    auth_provider: str  # "credentials" | "google" | "both"
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True)


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    image: Optional[str] = None
    auth_provider: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
