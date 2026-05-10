from __future__ import annotations

import hashlib
from typing import Any

from app.clients.business.base import BusinessClientError, _BusinessClientBase
from app.models.financial.partner import (
    PartnerCreate,
    PartnerKind,
    PartnerListResponse,
    PartnerResolveRequest,
    PartnerResolveResponse,
    PartnerResponse,
)
from app.models.financial.receipt import ExtractedPartnerDraft, PartnerUpsertResult


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


def _merge_supplier_kind(kind: PartnerKind) -> PartnerKind:
    if kind == "client":
        return "both"
    return kind


class _PartnersClient(_BusinessClientBase):
    async def list_partners(
        self,
        user_id: str,
        *,
        company_id: str,
        kind: PartnerKind | None,
        query: str | None,
        limit: int,
        offset: int = 0,
    ) -> PartnerListResponse:
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
        return PartnerListResponse.model_validate(data)

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

    async def resolve_partner(self, user_id: str, payload: PartnerResolveRequest) -> PartnerResolveResponse:
        data = await self._request("POST", "/partners/resolve", user_id, json=payload.model_dump(mode="json"))
        return PartnerResolveResponse.model_validate(data)

    async def update_partner(
        self,
        *,
        user_id: str,
        company_id: str,
        partner_id: str,
        payload: dict[str, Any],
    ) -> PartnerResponse:
        data = await self._request(
            "PATCH",
            f"/partners/{partner_id}",
            user_id,
            params={"company_id": company_id},
            json=payload,
        )
        return PartnerResponse.model_validate(data)

    def _build_supplier_partner_update(
        self,
        *,
        existing: PartnerResponse,
        vendor: ExtractedPartnerDraft,
    ) -> dict[str, Any]:
        update_payload: dict[str, Any] = {}

        if existing.kind != "supplier" and existing.kind != "both":
            update_payload["kind"] = _merge_supplier_kind(existing.kind)

        # Only persist confirmed non-empty edits to avoid destructive blank overwrites.
        if name := _optional_extracted(vendor.name):
            update_payload["name"] = name
        if registration_number := _optional_extracted(vendor.registration_number):
            if registration_number != existing.registration_number:
                update_payload["registration_number"] = registration_number
        if vat_number := _optional_extracted(vendor.vat_number):
            update_payload["vat_number"] = vat_number
        if city := _optional_extracted(vendor.city):
            update_payload["city"] = city
        if country := _optional_extracted(vendor.country):
            update_payload["country"] = country
        if address := _optional_extracted(vendor.address):
            update_payload["address"] = address
        if accountable_person := _optional_extracted(vendor.accountable_person):
            update_payload["accountable_person"] = accountable_person
        if email := _optional_extracted(vendor.email):
            update_payload["email"] = email
        if phone := _optional_extracted(vendor.phone):
            update_payload["phone"] = phone

        return update_payload

    async def find_matching_supplier_partner(
        self,
        *,
        user_id: str,
        company_id: str,
        vendor: ExtractedPartnerDraft,
    ) -> PartnerResponse | None:
        resolved = await self.resolve_partner(
            user_id=user_id,
            payload=PartnerResolveRequest(
                company_id=company_id,
                kind="supplier",
                registration_number=vendor.registration_number,
                vat_number=vendor.vat_number,
                name=vendor.name,
                limit=5,
            ),
        )
        if not resolved.candidates:
            return None
        top_candidate = resolved.candidates[0]
        if top_candidate.match_type in {"id", "registration_number_exact", "vat_exact"}:
            return top_candidate.partner
        if len(resolved.candidates) == 1 and top_candidate.score >= 0.9:
            return top_candidate.partner
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
            update_payload = self._build_supplier_partner_update(existing=existing, vendor=vendor)
            if update_payload:
                existing = await self.update_partner(
                    user_id=user_id,
                    company_id=company_id,
                    partner_id=existing.id,
                    payload=update_payload,
                )
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
