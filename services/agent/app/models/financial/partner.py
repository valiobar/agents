from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.common import ListEnvelope

PartnerKind = Literal["client", "supplier", "both", "other"]


def _none_if_blank(value: object) -> object | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


class PartnerCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=64)
    kind: PartnerKind = "client"
    name: str = Field(min_length=1, max_length=200)
    registration_number: str = Field(min_length=1, max_length=64)
    vat_number: str | None = Field(default=None, max_length=64)
    city: str = Field(min_length=1, max_length=120)
    country: str = Field(default="Bulgaria", min_length=1, max_length=120)
    address: str = Field(min_length=1, max_length=500)
    accountable_person: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator(
        "vat_number",
        "phone",
        "email",
        "notes",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, value: object) -> object | None:
        return _none_if_blank(value)


class PartnerResponse(PartnerCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime


PartnerListResponse = ListEnvelope[PartnerResponse]

PartnerMatchType = Literal[
    "id",
    "registration_number_exact",
    "vat_exact",
    "name_exact",
    "name_prefix",
    "contains",
]


class PartnerResolveRequest(BaseModel):
    company_id: str = Field(min_length=1, max_length=64)
    kind: PartnerKind | None = None
    partner_id: str | None = Field(default=None, min_length=1, max_length=64)
    registration_number: str | None = Field(default=None, min_length=1, max_length=64)
    vat_number: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    limit: int = Field(default=5, ge=1, le=10)


class PartnerMatchCandidate(BaseModel):
    partner: PartnerResponse
    match_type: PartnerMatchType
    score: float = Field(ge=0, le=1)
    match_reasons: list[str] = Field(default_factory=list)


class PartnerResolveResponse(BaseModel):
    candidates: list[PartnerMatchCandidate] = Field(default_factory=list)
