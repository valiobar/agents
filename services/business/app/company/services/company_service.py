from __future__ import annotations

from fastapi import HTTPException, status

from app.company.models import CompanyCreate, CompanyInDB, CompanyUpdate
from app.company.repositories.company_repo import CompanyRepository
from app.financial.repositories.invoice_repo import InvoiceRepository
from app.partner.repositories.partner_repo import PartnerRepository

_COMPANY_NOT_FOUND_DETAIL = "Company not found"


class CompanyService:
    def __init__(
        self,
        company_repo: CompanyRepository,
        invoice_repo: InvoiceRepository,
        partner_repo: PartnerRepository,
    ) -> None:
        self.company_repo = company_repo
        self.invoice_repo = invoice_repo
        self.partner_repo = partner_repo

    async def create_company(self, user_id: str, payload: CompanyCreate) -> CompanyInDB:
        return await self.company_repo.create(user_id, payload)

    async def list_companies(self, user_id: str, limit: int, offset: int) -> list[CompanyInDB]:
        return await self.company_repo.list_by_user(user_id, limit, offset)

    async def require_company(self, user_id: str, company_id: str) -> CompanyInDB:
        company = await self.company_repo.get_by_id(user_id, company_id)
        if company is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_COMPANY_NOT_FOUND_DETAIL)
        return company

    async def update_company(self, user_id: str, company_id: str, payload: CompanyUpdate) -> CompanyInDB:
        updated = await self.company_repo.update(user_id, company_id, payload)
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_COMPANY_NOT_FOUND_DETAIL)
        return updated

    async def delete_company(self, user_id: str, company_id: str) -> None:
        await self.require_company(user_id, company_id)

        # TODO(phase-5): restore assigned-agent delete protection via internal Agent API if required.
        if await self.invoice_repo.count_by_company(user_id, company_id) > 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Company has invoices")
        if await self.partner_repo.count_by_company(user_id, company_id) > 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Company has partners")

        deleted = await self.company_repo.delete(user_id, company_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_COMPANY_NOT_FOUND_DETAIL)
