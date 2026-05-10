from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.common.models import ListEnvelope
from app.dependencies import get_partner_service, get_user_id
from app.partner.models import (
    PartnerCreate,
    PartnerKind,
    PartnerResolveRequest,
    PartnerResolveResponse,
    PartnerResponse,
    PartnerUpdate,
)
from app.partner.services.partner_service import PartnerService

router = APIRouter(prefix="/partners", tags=["partners"])
PartnerListResponse = ListEnvelope[PartnerResponse]


@router.post("", response_model=PartnerResponse, status_code=status.HTTP_201_CREATED)
async def create_partner(
    payload: PartnerCreate,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[PartnerService, Depends(get_partner_service)],
):
    partner = await service.create_partner(user_id, payload)
    return PartnerResponse.model_validate(partner)


@router.get("", response_model=PartnerListResponse)
async def list_partners(
    company_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[PartnerService, Depends(get_partner_service)],
    kind: PartnerKind | None = None,
    query: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    result = await service.list_partners_envelope(
        user_id=user_id,
        company_id=company_id,
        kind=kind,
        query=query,
        limit=limit,
        offset=offset,
    )
    return PartnerListResponse(
        total_count=result.total_count,
        returned_count=result.returned_count,
        offset=result.offset,
        limit=result.limit,
        truncated=result.truncated,
        next_offset=result.next_offset,
        items=[PartnerResponse.model_validate(partner) for partner in result.items],
    )


@router.get("/{partner_id}", response_model=PartnerResponse)
async def get_partner(
    partner_id: str,
    company_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[PartnerService, Depends(get_partner_service)],
):
    partner = await service.get_partner(user_id, company_id, partner_id)
    return PartnerResponse.model_validate(partner)


@router.patch("/{partner_id}", response_model=PartnerResponse)
async def update_partner(
    partner_id: str,
    payload: PartnerUpdate,
    company_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[PartnerService, Depends(get_partner_service)],
):
    partner = await service.update_partner(user_id, company_id, partner_id, payload)
    return PartnerResponse.model_validate(partner)


@router.delete("/{partner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_partner(
    partner_id: str,
    company_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[PartnerService, Depends(get_partner_service)],
):
    await service.delete_partner(user_id, company_id, partner_id)
    return None


@router.post("/resolve", response_model=PartnerResolveResponse)
async def resolve_partner(
    payload: PartnerResolveRequest,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[PartnerService, Depends(get_partner_service)],
):
    return await service.resolve_partner(user_id=user_id, payload=payload)
