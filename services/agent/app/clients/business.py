from __future__ import annotations

from typing import Any

import httpx

from app.models.company import CompanyResponse
from app.models.financial import (
    ExpenseCreate,
    ExpenseFilters,
    ExpenseResponse,
    FinancialSummaryRequest,
    FinancialSummaryResponse,
    InvoiceCreate,
    InvoiceFilters,
    InvoiceResponse,
)
from app.models.partner import PartnerCreate, PartnerKind, PartnerResponse


class BusinessClientError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class BusinessClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    def _headers(self, user_id: str) -> dict[str, str]:
        return {"x-user-id": user_id}

    async def _request(self, method: str, path: str, user_id: str, **kwargs: Any) -> Any:
        try:
            response = await self.http.request(method, path, headers=self._headers(user_id), **kwargs)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = self._extract_detail(exc.response)
            raise BusinessClientError(detail, status_code=exc.response.status_code) from exc
        except httpx.HTTPError as exc:
            raise BusinessClientError("Business service is unavailable. Try again shortly.") from exc
        return response.json()

    def _extract_detail(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return "Business service returned an unexpected response."
        detail = data.get("detail") if isinstance(data, dict) else None
        return str(detail or "Business request failed.")

    async def list_companies(
        self,
        user_id: str,
        *,
        limit: int,
        offset: int = 0,
    ) -> list[CompanyResponse]:
        data = await self._request("GET", "/companies", user_id, params={"limit": limit, "offset": offset})
        return [CompanyResponse.model_validate(item) for item in data]

    async def company_exists(self, user_id: str, company_id: str) -> bool:
        data = await self._request("GET", f"/companies/{company_id}/exists", user_id)
        return bool(data.get("exists")) if isinstance(data, dict) else False

    async def list_partners(
        self,
        user_id: str,
        *,
        company_id: str,
        kind: PartnerKind | None,
        query: str | None,
        limit: int,
        offset: int = 0,
    ) -> list[PartnerResponse]:
        params = {
            "company_id": company_id,
            "kind": kind,
            "query": query,
            "limit": limit,
            "offset": offset,
        }
        data = await self._request(
            "GET",
            "/partners",
            user_id,
            params={key: value for key, value in params.items() if value is not None},
        )
        return [PartnerResponse.model_validate(item) for item in data]

    async def get_partner(
        self,
        user_id: str,
        *,
        company_id: str,
        partner_id: str,
    ) -> PartnerResponse:
        data = await self._request("GET", f"/partners/{partner_id}", user_id, params={"company_id": company_id})
        return PartnerResponse.model_validate(data)

    async def create_partner(self, user_id: str, payload: PartnerCreate) -> PartnerResponse:
        data = await self._request("POST", "/partners", user_id, json=payload.model_dump(mode="json"))
        return PartnerResponse.model_validate(data)

    async def list_invoices(
        self,
        user_id: str,
        filters: InvoiceFilters,
        *,
        limit: int,
        offset: int = 0,
    ) -> list[InvoiceResponse]:
        params = filters.model_dump(mode="json", exclude_none=True) | {"limit": limit, "offset": offset}
        data = await self._request("GET", "/invoices", user_id, params=params)
        return [InvoiceResponse.model_validate(item) for item in data]

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
    ) -> list[ExpenseResponse]:
        params = filters.model_dump(mode="json", exclude_none=True) | {"limit": limit, "offset": offset}
        data = await self._request("GET", "/expenses", user_id, params=params)
        return [ExpenseResponse.model_validate(item) for item in data]

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
