from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status

from app.financial.models import ExpenseCreate, ExpenseFilters, ExpenseInDB, ExpenseItem
from app.financial.repositories.expense_repo import ExpenseRepository
from app.financial.repositories.financial_utils import quantize_money, quantize_rate

_EXPENSE_NOT_FOUND_DETAIL = "Expense not found"


class ExpenseService:
    def __init__(self, repo: ExpenseRepository) -> None:
        self.repo = repo

    def _calculate_items(self, payload: ExpenseCreate) -> tuple[list[ExpenseItem] | None, Decimal]:
        if not payload.items:
            amount = payload.amount
            # Model validation enforces "amount or items", but keep the calculation total.
            if amount is None:
                amount = Decimal("0")
            return None, quantize_money(amount)

        items: list[ExpenseItem] = []
        amount = Decimal("0")
        for item in payload.items:
            line_total = quantize_money(item.quantity * item.unit_price)
            items.append(ExpenseItem(**item.model_dump(), total=line_total))
            amount += line_total
        return items, quantize_money(amount)

    def _deductible_amount(self, payload: ExpenseCreate, amount: Decimal) -> Decimal:
        if not payload.deductible:
            return Decimal("0.00")
        return quantize_money(amount * quantize_rate(payload.deductible_rate))

    async def create_expense(self, user_id: str, payload: ExpenseCreate) -> ExpenseInDB:
        items, amount = self._calculate_items(payload)
        doc = payload.model_dump(exclude={"items"}, mode="python")
        doc.update(
            {
                "user_id": user_id,
                "amount": amount,
                "items": [item.model_dump(mode="python") for item in items] if items else None,
                "deductible_amount": self._deductible_amount(payload, amount),
            }
        )
        return await self.repo.create(doc)

    async def list_expenses(
        self, user_id: str, filters: ExpenseFilters, limit: int, offset: int
    ) -> list[ExpenseInDB]:
        return await self.repo.list_by_user(user_id, filters, limit, offset)

    async def get_expense(self, user_id: str, expense_id: str) -> ExpenseInDB:
        expense = await self.repo.get_by_id(user_id, expense_id)
        if expense is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_EXPENSE_NOT_FOUND_DETAIL,
            )
        return expense
