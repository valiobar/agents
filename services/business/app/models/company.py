from __future__ import annotations

import base64
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

_ALLOWED_LOGO_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
_MAX_LOGO_BYTES = 256 * 1024


def _none_if_blank(value: object) -> object | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def _validate_logo_data_url(value: str | None) -> str | None:
    if value is None:
        return None

    header, sep, payload = value.partition(",")
    if sep != "," or not header.startswith("data:") or ";base64" not in header:
        raise ValueError("logo_data_url must be a base64 data URL")

    media_type = header.removeprefix("data:").split(";", 1)[0]
    if media_type not in _ALLOWED_LOGO_TYPES:
        raise ValueError("Unsupported logo image type")

    try:
        decoded = base64.b64decode(payload, validate=True)
    except ValueError as exc:
        raise ValueError("Invalid logo base64 payload") from exc

    if len(decoded) > _MAX_LOGO_BYTES:
        raise ValueError("Logo must be 256 KB or smaller")

    return value


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    registration_number: str = Field(min_length=1, max_length=64)
    vat_number: str | None = Field(default=None, max_length=64)
    city: str = Field(min_length=1, max_length=120)
    country: str = Field(default="Bulgaria", min_length=1, max_length=120)
    address: str = Field(min_length=1, max_length=500)
    accountable_person: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=64)
    logo_data_url: str | None = None
    is_default: bool = False

    @field_validator("vat_number", "phone", "email", "logo_data_url", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: object) -> object | None:
        return _none_if_blank(value)

    @field_validator("logo_data_url")
    @classmethod
    def validate_logo(cls, value: str | None) -> str | None:
        return _validate_logo_data_url(value)


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    registration_number: str | None = Field(default=None, min_length=1, max_length=64)
    vat_number: str | None = Field(default=None, max_length=64)
    city: str | None = Field(default=None, min_length=1, max_length=120)
    country: str | None = Field(default=None, min_length=1, max_length=120)
    address: str | None = Field(default=None, min_length=1, max_length=500)
    accountable_person: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=64)
    logo_data_url: str | None = None
    is_default: bool | None = None

    @field_validator("name", "registration_number", "vat_number", "city", "country", "address", "accountable_person", "phone", "email", "logo_data_url", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: object) -> object | None:
        return _none_if_blank(value)

    @field_validator("logo_data_url")
    @classmethod
    def validate_logo(cls, value: str | None) -> str | None:
        return _validate_logo_data_url(value)


class CompanyInDB(CompanyCreate):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime


class CompanyResponse(CompanyInDB):
    model_config = ConfigDict(from_attributes=True)

