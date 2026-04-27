from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import settings
from app.repositories.agent_repo import AgentRepository
from app.repositories.company_repo import CompanyRepository
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.expense_repo import ExpenseRepository
from app.repositories.invoice_repo import InvoiceRepository
from app.repositories.partner_repo import PartnerRepository
from app.runtime.tool_context import ToolContext
from app.services.agent_service import AgentService
from app.services.companybook_service import CompanyBookService
from app.services.chat_service import ChatService
from app.services.company_service import CompanyService
from app.services.conversation_service import ConversationService
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


def get_agent_repo(db: AsyncIOMotorDatabase = Depends(get_db)) -> AgentRepository:
    return AgentRepository(db)


def get_company_repo(db: AsyncIOMotorDatabase = Depends(get_db)) -> CompanyRepository:
    return CompanyRepository(db)


def get_conversation_repo(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ConversationRepository:
    return ConversationRepository(db)


def get_invoice_repo(db: AsyncIOMotorDatabase = Depends(get_db)) -> InvoiceRepository:
    return InvoiceRepository(db)


def get_expense_repo(db: AsyncIOMotorDatabase = Depends(get_db)) -> ExpenseRepository:
    return ExpenseRepository(db)


def get_partner_repo(db: AsyncIOMotorDatabase = Depends(get_db)) -> PartnerRepository:
    return PartnerRepository(db)


def get_expense_service(repo: ExpenseRepository = Depends(get_expense_repo)) -> ExpenseService:
    return ExpenseService(repo)


def get_financial_summary_service(
    invoice_repo: InvoiceRepository = Depends(get_invoice_repo),
    expense_repo: ExpenseRepository = Depends(get_expense_repo),
) -> FinancialSummaryService:
    return FinancialSummaryService(invoice_repo, expense_repo)


def get_agent_service(
    repo: AgentRepository = Depends(get_agent_repo),
    company_repo: CompanyRepository = Depends(get_company_repo),
) -> AgentService:
    return AgentService(repo, company_repo=company_repo)


def get_company_service(
    company_repo: CompanyRepository = Depends(get_company_repo),
    agent_repo: AgentRepository = Depends(get_agent_repo),
    invoice_repo: InvoiceRepository = Depends(get_invoice_repo),
) -> CompanyService:
    return CompanyService(company_repo=company_repo, agent_repo=agent_repo, invoice_repo=invoice_repo)


def get_invoice_service(
    repo: InvoiceRepository = Depends(get_invoice_repo),
    company_service: CompanyService = Depends(get_company_service),
    partner_repo: PartnerRepository = Depends(get_partner_repo),
) -> InvoiceService:
    return InvoiceService(repo, company_service=company_service, partner_repo=partner_repo)


def get_partner_service(
    partner_repo: PartnerRepository = Depends(get_partner_repo),
    company_service: CompanyService = Depends(get_company_service),
    invoice_repo: InvoiceRepository = Depends(get_invoice_repo),
) -> PartnerService:
    return PartnerService(partner_repo=partner_repo, company_service=company_service, invoice_repo=invoice_repo)


def get_companybook_service() -> CompanyBookService:
    return CompanyBookService(
        api_key=settings.companybook_api_key,
        base_url=settings.companybook_base_url,
        timeout=settings.companybook_timeout_seconds,
    )


def get_tool_context(
    invoice_service: InvoiceService = Depends(get_invoice_service),
    expense_service: ExpenseService = Depends(get_expense_service),
    summary_service: FinancialSummaryService = Depends(get_financial_summary_service),
    partner_service: PartnerService = Depends(get_partner_service),
    company_service: CompanyService = Depends(get_company_service),
    companybook_service: CompanyBookService = Depends(get_companybook_service),
) -> ToolContext:
    return ToolContext(
        invoice_service=invoice_service,
        expense_service=expense_service,
        summary_service=summary_service,
        partner_service=partner_service,
        company_service=company_service,
        companybook_service=companybook_service,
    )


def get_chat_service(
    agent_repo: AgentRepository = Depends(get_agent_repo),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    tool_context: ToolContext = Depends(get_tool_context),
) -> ChatService:
    return ChatService(agent_repo, conversation_repo, tool_context)


def get_conversation_service(
    repo: ConversationRepository = Depends(get_conversation_repo),
) -> ConversationService:
    return ConversationService(repo)

