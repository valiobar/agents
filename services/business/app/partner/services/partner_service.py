from __future__ import annotations

from fastapi import HTTPException, status

from app.common.models import ListEnvelope, make_list_envelope
from app.company.services.company_service import CompanyService
from app.financial.repositories.invoice_repo import InvoiceRepository
from app.partner.models import (
    PartnerCreate,
    PartnerInDB,
    PartnerKind,
    PartnerMatchCandidate,
    PartnerMatchType,
    PartnerResolveRequest,
    PartnerResolveResponse,
    PartnerUpdate,
)
from app.partner.repositories.partner_repo import PartnerRepository
from app.common.search import normalize_search_key, normalize_search_text

_PARTNER_NOT_FOUND_DETAIL = "Partner not found"


class PartnerService:
    def __init__(
        self,
        partner_repo: PartnerRepository,
        company_service: CompanyService,
        invoice_repo: InvoiceRepository,
    ) -> None:
        self.partner_repo = partner_repo
        self.company_service = company_service
        self.invoice_repo = invoice_repo

    async def create_partner(self, user_id: str, payload: PartnerCreate) -> PartnerInDB:
        await self.company_service.require_company(user_id, payload.company_id)
        return await self.partner_repo.create(user_id, payload)

    async def list_partners(
        self,
        user_id: str,
        company_id: str,
        kind: PartnerKind | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> list[PartnerInDB]:
        await self.company_service.require_company(user_id, company_id)
        return await self.partner_repo.list_by_company(user_id, company_id, kind, query, limit, offset)

    async def list_partners_envelope(
        self,
        user_id: str,
        company_id: str,
        kind: PartnerKind | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> ListEnvelope[PartnerInDB]:
        await self.company_service.require_company(user_id, company_id)
        items = await self.partner_repo.list_by_company(user_id, company_id, kind, query, limit, offset)
        total_count = await self.partner_repo.count_by_company_filters(user_id, company_id, kind, query)
        return make_list_envelope(items=items, total_count=total_count, offset=offset, limit=limit)

    async def get_partner(self, user_id: str, company_id: str, partner_id: str) -> PartnerInDB:
        await self.company_service.require_company(user_id, company_id)
        partner = await self.partner_repo.get_by_id(user_id, partner_id)
        if partner is None or partner.company_id != company_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_PARTNER_NOT_FOUND_DETAIL)
        return partner

    async def update_partner(
        self, user_id: str, company_id: str, partner_id: str, payload: PartnerUpdate
    ) -> PartnerInDB:
        await self.get_partner(user_id, company_id, partner_id)
        updated = await self.partner_repo.update(user_id, partner_id, payload)
        if updated is None or updated.company_id != company_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_PARTNER_NOT_FOUND_DETAIL)
        return updated

    async def delete_partner(self, user_id: str, company_id: str, partner_id: str) -> None:
        await self.get_partner(user_id, company_id, partner_id)

        if await self.invoice_repo.count_by_partner(user_id, company_id, partner_id) > 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Partner has invoices")

        deleted = await self.partner_repo.delete(user_id, partner_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_PARTNER_NOT_FOUND_DETAIL)

    def _candidate_match(self, partner: PartnerInDB, payload: PartnerResolveRequest) -> tuple[PartnerMatchType, float, list[str]]:
        reasons: list[str] = []
        if payload.partner_id and partner.id == payload.partner_id:
            reasons.append("Partner id matches exactly.")
            return "id", 1.0, reasons

        payload_registration = normalize_search_key(payload.registration_number)
        partner_registration = normalize_search_key(partner.registration_number)
        if payload_registration and partner_registration == payload_registration:
            reasons.append("Registration number matches exactly.")
            return "registration_number_exact", 0.99, reasons

        payload_vat = normalize_search_key(payload.vat_number)
        partner_vat = normalize_search_key(partner.vat_number)
        if payload_vat and partner_vat == payload_vat:
            reasons.append("VAT number matches exactly.")
            return "vat_exact", 0.98, reasons

        payload_name = normalize_search_text(payload.name)
        partner_name = normalize_search_text(partner.name)
        if payload_name and partner_name == payload_name:
            reasons.append("Name matches exactly.")
            return "name_exact", 0.92, reasons
        if payload_name and partner_name and partner_name.startswith(payload_name):
            reasons.append("Name starts with the search text.")
            return "name_prefix", 0.8, reasons

        reasons.append("Search text is contained in the partner fields.")
        return "contains", 0.6, reasons

    async def resolve_partner(self, user_id: str, payload: PartnerResolveRequest) -> PartnerResolveResponse:
        await self.company_service.require_company(user_id, payload.company_id)
        candidates = await self.partner_repo.resolve_candidates(user_id=user_id, payload=payload)
        scored = [
            PartnerMatchCandidate(
                partner=partner,
                match_type=match_type,
                score=score,
                match_reasons=match_reasons,
            )
            for partner in candidates
            for match_type, score, match_reasons in [self._candidate_match(partner, payload)]
        ]
        scored.sort(key=lambda candidate: candidate.score, reverse=True)
        return PartnerResolveResponse(candidates=scored[: payload.limit])
