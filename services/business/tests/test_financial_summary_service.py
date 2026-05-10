from __future__ import annotations

import sys
import unittest
from asyncio import sleep
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.financial.models import FinancialSummaryRequest
from app.financial.services.financial_summary_service import FinancialSummaryService


@dataclass
class _RequestCapture:
    company_id: str | None = None
    partner_id: str | None = None
    include_invoices: bool | None = None
    include_expenses: bool | None = None


class _FakeInvoiceRepo:
    def __init__(self) -> None:
        self.last_request: _RequestCapture | None = None

    async def aggregate_summary(self, user_id: str, request: FinancialSummaryRequest) -> list[dict]:
        await sleep(0)
        self.last_request = _RequestCapture(
            company_id=request.company_id,
            partner_id=request.partner_id,
            include_invoices=request.include_invoices,
            include_expenses=request.include_expenses,
        )
        return [{"key": "all", "currency": "EUR", "invoice_total": Decimal("120.00")}]


class _FakeExpenseRepo:
    def __init__(self) -> None:
        self.last_request: _RequestCapture | None = None

    async def aggregate_summary(self, user_id: str, request: FinancialSummaryRequest) -> list[dict]:
        await sleep(0)
        self.last_request = _RequestCapture(
            company_id=request.company_id,
            partner_id=request.partner_id,
            include_invoices=request.include_invoices,
            include_expenses=request.include_expenses,
        )
        return [
            {
                "key": "all",
                "currency": "EUR",
                "expense_total": Decimal("10.00"),
                "deductible_expense_total": Decimal("5.00"),
            }
        ]


class _FakeCompanyService:
    def __init__(self) -> None:
        self.required_company_id: str | None = None

    async def require_company(self, user_id: str, company_id: str) -> object:
        await sleep(0)
        self.required_company_id = company_id
        return object()


class _FakePartnerService:
    def __init__(self) -> None:
        self.required_company_id: str | None = None
        self.required_partner_id: str | None = None

    async def get_partner(self, user_id: str, company_id: str, partner_id: str) -> object:
        await sleep(0)
        self.required_company_id = company_id
        self.required_partner_id = partner_id
        return object()


class FinancialSummaryServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_summary_is_eur_and_applies_company_partner_filters(self) -> None:
        invoice_repo = _FakeInvoiceRepo()
        expense_repo = _FakeExpenseRepo()
        company_service = _FakeCompanyService()
        partner_service = _FakePartnerService()
        service = FinancialSummaryService(invoice_repo, expense_repo, company_service, partner_service)

        request = FinancialSummaryRequest(
            company_id="company-1",
            partner_id="partner-1",
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
            include_invoices=True,
            include_expenses=True,
        )
        summary = await service.get_summary("user-1", request)

        self.assertEqual(summary.currency, "EUR")
        self.assertEqual(summary.invoice_total, Decimal("120.00"))
        self.assertEqual(summary.expense_total, Decimal("10.00"))
        self.assertEqual(summary.deductible_expense_total, Decimal("5.00"))
        self.assertEqual(summary.net_total, Decimal("110.00"))
        self.assertIsNotNone(invoice_repo.last_request)
        self.assertIsNotNone(expense_repo.last_request)
        self.assertEqual(invoice_repo.last_request.company_id, "company-1")
        self.assertEqual(invoice_repo.last_request.partner_id, "partner-1")
        self.assertEqual(expense_repo.last_request.company_id, "company-1")
        self.assertEqual(expense_repo.last_request.partner_id, "partner-1")
        self.assertEqual(company_service.required_company_id, "company-1")
        self.assertEqual(partner_service.required_company_id, "company-1")
        self.assertEqual(partner_service.required_partner_id, "partner-1")


if __name__ == "__main__":
    unittest.main()
