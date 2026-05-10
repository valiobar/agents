from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status

from app.common.models import ListEnvelope, make_list_envelope
from app.company.services.company_service import CompanyService
from app.financial.models import ExpenseCreate, ExpenseFilters, ExpenseInDB, ExpenseItem
from app.financial.repositories.expense_repo import ExpenseRepository
from app.financial.repositories.financial_utils import quantize_money, quantize_rate
from app.partner.repositories.partner_repo import PartnerRepository

_EXPENSE_NOT_FOUND_DETAIL = "Expense not found"


class ExpenseService:
    def __init__(
        self,
        repo: ExpenseRepository,
        company_service: CompanyService,
        partner_repo: PartnerRepository,
    ) -> None:
        self.repo = repo
        self.company_service = company_service
        self.partner_repo = partner_repo

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
        await self.company_service.require_company(user_id, payload.company_id)
        if payload.partner_id:
            partner = await self.partner_repo.get_by_id(user_id, payload.partner_id)
            if partner is None or partner.company_id != payload.company_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Partner not found")
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
        await self.company_service.require_company(user_id, filters.company_id)
        return await self.repo.list_by_user(user_id, filters, limit, offset)

    async def list_expenses_envelope(
        self, user_id: str, filters: ExpenseFilters, limit: int, offset: int
    ) -> ListEnvelope[ExpenseInDB]:
        await self.company_service.require_company(user_id, filters.company_id)
        items = await self.repo.list_by_user(user_id, filters, limit, offset)
        total_count = await self.repo.count_by_user(user_id, filters)
        return make_list_envelope(items=items, total_count=total_count, offset=offset, limit=limit)

    async def get_expense(self, user_id: str, expense_id: str) -> ExpenseInDB:
        expense = await self.repo.get_by_id(user_id, expense_id)
        if expense is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=_EXPENSE_NOT_FOUND_DETAIL,
            )
        return expense
