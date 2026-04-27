from __future__ import annotations

from fastapi import HTTPException, status

from app.models.partner import PartnerCreate, PartnerInDB, PartnerKind, PartnerUpdate
from app.repositories.invoice_repo import InvoiceRepository
from app.repositories.partner_repo import PartnerRepository
from app.services.company_service import CompanyService

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

