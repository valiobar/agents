from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_company_service, get_user_id
from app.company.models import CompanyCreate, CompanyResponse, CompanyUpdate
from app.company.services.company_service import CompanyService

router = APIRouter(prefix="/companies", tags=["companies"])


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: CompanyCreate,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[CompanyService, Depends(get_company_service)],
):
    company = await service.create_company(user_id, payload)
    return CompanyResponse.model_validate(company)


@router.get("", response_model=list[CompanyResponse])
async def list_companies(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[CompanyService, Depends(get_company_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    companies = await service.list_companies(user_id, limit, offset)
    return [CompanyResponse.model_validate(company) for company in companies]


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[CompanyService, Depends(get_company_service)],
):
    company = await service.require_company(user_id, company_id)
    return CompanyResponse.model_validate(company)


@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: str,
    payload: CompanyUpdate,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[CompanyService, Depends(get_company_service)],
):
    company = await service.update_company(user_id, company_id, payload)
    return CompanyResponse.model_validate(company)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[CompanyService, Depends(get_company_service)],
):
    await service.delete_company(user_id, company_id)
    return None


@router.get("/{company_id}/exists", response_model=dict[str, bool])
async def company_exists(
    company_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[CompanyService, Depends(get_company_service)],
):
    await service.require_company(user_id, company_id)
    return {"exists": True}
