from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_expense_service, get_user_id
from app.models.financial import ExpenseCategory, ExpenseCreate, ExpenseFilters, ExpenseResponse
from app.services.expense_service import ExpenseService

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.post("", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    payload: ExpenseCreate,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[ExpenseService, Depends(get_expense_service)],
):
    expense = await service.create_expense(user_id, payload)
    return ExpenseResponse.model_validate(expense)


@router.get("", response_model=list[ExpenseResponse])
async def list_expenses(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[ExpenseService, Depends(get_expense_service)],
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
        category=category,
        counterparty=counterparty,
        date_from=date_from,
        date_to=date_to,
        deductible=deductible,
        amount_min=amount_min,
        amount_max=amount_max,
    )
    expenses = await service.list_expenses(user_id, filters, limit, offset)
    return [ExpenseResponse.model_validate(expense) for expense in expenses]


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    expense_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[ExpenseService, Depends(get_expense_service)],
):
    expense = await service.get_expense(user_id, expense_id)
    return ExpenseResponse.model_validate(expense)
