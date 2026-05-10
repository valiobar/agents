from __future__ import annotations

from app.clients.business.base import _BusinessClientBase
from app.models.financial import (
    ExpenseCreate,
    ExpenseFilters,
    ExpenseListResponse,
    ExpenseResponse,
    FinancialSummaryRequest,
    FinancialSummaryResponse,
    InvoiceCreate,
    InvoiceFilters,
    InvoiceListResponse,
    InvoiceResponse,
)


class _FinancialClient(_BusinessClientBase):
    async def list_invoices(
        self,
        user_id: str,
        filters: InvoiceFilters,
        *,
        limit: int,
        offset: int = 0,
    ) -> InvoiceListResponse:
        params = filters.model_dump(mode="json", exclude_none=True) | {"limit": limit, "offset": offset}
        data = await self._request("GET", "/invoices", user_id, params=params)
        return InvoiceListResponse.model_validate(data)

    async def create_invoice(self, user_id: str, payload: InvoiceCreate) -> InvoiceResponse:
        data = await self._request("POST", "/invoices", user_id, json=payload.model_dump(mode="json"))
        return InvoiceResponse.model_validate(data)

    async def list_expenses(
        self,
        user_id: str,
        filters: ExpenseFilters,
        *,
        limit: int,
        offset: int = 0,
    ) -> ExpenseListResponse:
        params = filters.model_dump(mode="json", exclude_none=True) | {"limit": limit, "offset": offset}
        data = await self._request("GET", "/expenses", user_id, params=params)
        return ExpenseListResponse.model_validate(data)

    async def create_expense(self, user_id: str, payload: ExpenseCreate) -> ExpenseResponse:
        data = await self._request("POST", "/expenses", user_id, json=payload.model_dump(mode="json"))
        return ExpenseResponse.model_validate(data)

    async def get_financial_summary(
        self,
        user_id: str,
        request: FinancialSummaryRequest,
    ) -> FinancialSummaryResponse:
        data = await self._request("POST", "/financial-summary", user_id, json=request.model_dump(mode="json"))
        return FinancialSummaryResponse.model_validate(data)
