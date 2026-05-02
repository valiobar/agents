from __future__ import annotations

import hashlib
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
from app.models.receipt import ExtractedPartnerDraft, PartnerUpsertResult


def _normalize_partner_key(value: str | None) -> str | None:
    normalized = " ".join(value.casefold().split()) if value else None
    return normalized or None


def _require_extracted(value: str | None, field_name: str) -> str:
    normalized = value.strip() if value else ""
    if not normalized:
        raise BusinessClientError(
            f"Invoice vendor partner is missing required field: {field_name}.",
            status_code=422,
        )
    return normalized


def _optional_extracted(value: str | None) -> str | None:
    normalized = value.strip() if value else ""
    return normalized or None


def _fallback_registration_number(name: str) -> str:
    digest = hashlib.sha1(name.casefold().encode("utf-8")).hexdigest()[:12]
    return f"extracted-{digest}"


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

    async def find_matching_supplier_partner(
        self,
        *,
        user_id: str,
        company_id: str,
        vendor: ExtractedPartnerDraft,
    ) -> PartnerResponse | None:
        candidates = await self.list_partners(
            user_id,
            company_id=company_id,
            kind=None,
            query=None,
            limit=100,
        )
        vendor_reg = _normalize_partner_key(vendor.registration_number)
        vendor_vat = _normalize_partner_key(vendor.vat_number)
        vendor_name = _normalize_partner_key(vendor.name)

        for partner in candidates:
            if vendor_reg and _normalize_partner_key(partner.registration_number) == vendor_reg:
                return partner
            if vendor_vat and _normalize_partner_key(partner.vat_number) == vendor_vat:
                return partner
        for partner in candidates:
            if vendor_name and _normalize_partner_key(partner.name) == vendor_name:
                return partner
        return None

    async def find_or_create_supplier_partner(
        self,
        *,
        user_id: str,
        company_id: str,
        vendor: ExtractedPartnerDraft,
    ) -> PartnerUpsertResult:
        existing = await self.find_matching_supplier_partner(
            user_id=user_id,
            company_id=company_id,
            vendor=vendor,
        )
        if existing:
            return PartnerUpsertResult(status="matched", partner=existing)

        payload = PartnerCreate(
            company_id=company_id,
            kind="supplier",
            name=_require_extracted(vendor.name, "name"),
            registration_number=_optional_extracted(vendor.registration_number)
            or _fallback_registration_number(vendor.name),
            vat_number=_optional_extracted(vendor.vat_number),
            city=_optional_extracted(vendor.city) or "Unknown",
            country=vendor.country or "Bulgaria",
            address=_optional_extracted(vendor.address) or "Unknown",
            accountable_person=_optional_extracted(vendor.accountable_person) or vendor.name,
            email=_optional_extracted(vendor.email),
            phone=_optional_extracted(vendor.phone),
            notes="Created from confirmed uploaded invoice extraction.",
        )
        created = await self.create_partner(user_id, payload)
        return PartnerUpsertResult(status="created", partner=created)

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
