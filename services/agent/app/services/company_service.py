from __future__ import annotations

from fastapi import HTTPException, status

from app.models.company import CompanyCreate, CompanyInDB, CompanyUpdate
from app.repositories.agent_repo import AgentRepository
from app.repositories.company_repo import CompanyRepository
from app.repositories.invoice_repo import InvoiceRepository

_COMPANY_NOT_FOUND_DETAIL = "Company not found"


class CompanyService:
    def __init__(
        self,
        company_repo: CompanyRepository,
        agent_repo: AgentRepository,
        invoice_repo: InvoiceRepository,
    ) -> None:
        self.company_repo = company_repo
        self.agent_repo = agent_repo
        self.invoice_repo = invoice_repo

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

        if await self.agent_repo.count_by_company(user_id, company_id) > 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Company has assigned agents")
        if await self.invoice_repo.count_by_company(user_id, company_id) > 0:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Company has invoices")

        deleted = await self.company_repo.delete(user_id, company_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_COMPANY_NOT_FOUND_DETAIL)

