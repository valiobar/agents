from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.company_repo import CompanyRepository
from app.repositories.expense_repo import ExpenseRepository
from app.repositories.invoice_repo import InvoiceRepository
from app.repositories.partner_repo import PartnerRepository
from app.services.company_service import CompanyService
from app.services.expense_service import ExpenseService
from app.services.financial_summary_service import FinancialSummaryService
from app.services.invoice_service import InvoiceService
from app.services.partner_service import PartnerService
from app.utils.db import get_database


def get_user_id(x_user_id: str | None = Header(default=None)) -> str:
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing x-user-id header",
        )
    return x_user_id


def get_db() -> AsyncIOMotorDatabase:
    return get_database()


def get_company_repo(db: AsyncIOMotorDatabase = Depends(get_db)) -> CompanyRepository:
    return CompanyRepository(db)


def get_invoice_repo(db: AsyncIOMotorDatabase = Depends(get_db)) -> InvoiceRepository:
    return InvoiceRepository(db)


def get_expense_repo(db: AsyncIOMotorDatabase = Depends(get_db)) -> ExpenseRepository:
    return ExpenseRepository(db)


def get_partner_repo(db: AsyncIOMotorDatabase = Depends(get_db)) -> PartnerRepository:
    return PartnerRepository(db)


def get_company_service(
    company_repo: CompanyRepository = Depends(get_company_repo),
    invoice_repo: InvoiceRepository = Depends(get_invoice_repo),
    partner_repo: PartnerRepository = Depends(get_partner_repo),
) -> CompanyService:
    return CompanyService(
        company_repo=company_repo,
        invoice_repo=invoice_repo,
        partner_repo=partner_repo,
    )


def get_invoice_service(
    repo: InvoiceRepository = Depends(get_invoice_repo),
    company_service: CompanyService = Depends(get_company_service),
    partner_repo: PartnerRepository = Depends(get_partner_repo),
) -> InvoiceService:
    return InvoiceService(
        repo,
        company_service=company_service,
        partner_repo=partner_repo,
    )


def get_expense_service(repo: ExpenseRepository = Depends(get_expense_repo)) -> ExpenseService:
    return ExpenseService(repo)


def get_partner_service(
    partner_repo: PartnerRepository = Depends(get_partner_repo),
    company_service: CompanyService = Depends(get_company_service),
    invoice_repo: InvoiceRepository = Depends(get_invoice_repo),
) -> PartnerService:
    return PartnerService(
        partner_repo=partner_repo,
        company_service=company_service,
        invoice_repo=invoice_repo,
    )


def get_financial_summary_service(
    invoice_repo: InvoiceRepository = Depends(get_invoice_repo),
    expense_repo: ExpenseRepository = Depends(get_expense_repo),
) -> FinancialSummaryService:
    return FinancialSummaryService(invoice_repo, expense_repo)
