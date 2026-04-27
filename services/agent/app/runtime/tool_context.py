from __future__ import annotations

from dataclasses import dataclass

from app.services.companybook_service import CompanyBookService
from app.services.company_service import CompanyService
from app.services.expense_service import ExpenseService
from app.services.financial_summary_service import FinancialSummaryService
from app.services.invoice_service import InvoiceService
from app.services.partner_service import PartnerService


@dataclass(frozen=True)
class ToolContext:
    invoice_service: InvoiceService
    expense_service: ExpenseService
    summary_service: FinancialSummaryService
    partner_service: PartnerService
    company_service: CompanyService
    companybook_service: CompanyBookService

