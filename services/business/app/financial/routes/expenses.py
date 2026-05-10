from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.common.models import ListEnvelope
from app.dependencies import get_expense_service, get_user_id
from app.financial.models import ExpenseCategory, ExpenseCreate, ExpenseFilters, ExpenseResponse
from app.financial.services.expense_service import ExpenseService

router = APIRouter(prefix="/expenses", tags=["expenses"])
ExpenseListResponse = ListEnvelope[ExpenseResponse]


@router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    payload: ExpenseCreate,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[ExpenseService, Depends(get_expense_service)],
):
    expense = await service.create_expense(user_id, payload)
    return ExpenseResponse.model_validate(expense)


@router.get("", response_model=ExpenseListResponse)
async def list_expenses(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[ExpenseService, Depends(get_expense_service)],
    company_id: str,
    partner_id: str | None = None,
    category: ExpenseCategory | None = None,
    counterparty: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    deductible: bool | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    filters = ExpenseFilters(
        company_id=company_id,
        partner_id=partner_id,
        category=category,
        counterparty=counterparty,
        date_from=date_from,
        date_to=date_to,
        deductible=deductible,
        amount_min=amount_min,
        amount_max=amount_max,
    )
    result = await service.list_expenses_envelope(user_id, filters, limit, offset)
    return ExpenseListResponse(
        total_count=result.total_count,
        returned_count=result.returned_count,
        offset=result.offset,
        limit=result.limit,
        truncated=result.truncated,
        next_offset=result.next_offset,
        items=[ExpenseResponse.model_validate(expense) for expense in result.items],
    )


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    expense_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[ExpenseService, Depends(get_expense_service)],
):
    expense = await service.get_expense(user_id, expense_id)
    return ExpenseResponse.model_validate(expense)
