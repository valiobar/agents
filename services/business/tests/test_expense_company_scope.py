from __future__ import annotations

import sys
import unittest
from asyncio import sleep
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.financial.models import ExpenseCreate, ExpenseFilters, ExpenseInDB
from app.financial.services.expense_service import ExpenseService


def _expense_in_db(company_id: str = "company-1", partner_id: str | None = None) -> ExpenseInDB:
    now = datetime.now(timezone.utc)
    return ExpenseInDB(
        id="expense-1",
        user_id="user-1",
        company_id=company_id,
        partner_id=partner_id,
        counterparty="Office Store",
        expense_date=date(2026, 4, 27),
        amount=Decimal("10.00"),
        currency="EUR",
        category="office",
        description=None,
        deductible=True,
        deductible_rate=Decimal("1.0"),
        source_document_type="receipt",
        source_document_id=None,
        source_document_number=None,
        items=None,
        deductible_amount=Decimal("10.00"),
        created_at=now,
        updated_at=now,
    )


class _FakeExpenseRepo:
    def __init__(self) -> None:
        self.last_list_filters: ExpenseFilters | None = None

    async def create(self, doc: dict) -> ExpenseInDB:
        await sleep(0)
        return _expense_in_db(company_id=doc["company_id"], partner_id=doc.get("partner_id"))

    async def list_by_user(self, user_id: str, filters: ExpenseFilters, limit: int, offset: int) -> list[ExpenseInDB]:
        await sleep(0)
        self.last_list_filters = filters
        return [_expense_in_db(company_id=filters.company_id, partner_id=filters.partner_id)]

    async def count_by_user(self, user_id: str, filters: ExpenseFilters) -> int:
        await sleep(0)
        return 1


class _FakeCompanyService:
    def __init__(self) -> None:
        self.required_company_id: str | None = None

    async def require_company(self, user_id: str, company_id: str) -> object:
        await sleep(0)
        self.required_company_id = company_id
        return object()


class _FailingCompanyService:
    async def require_company(self, user_id: str, company_id: str) -> object:
        await sleep(0)
        raise HTTPException(status_code=404, detail="Company not found")


class _FakePartnerRepo:
    def __init__(self, partner_company_id: str | None) -> None:
        self.partner_company_id = partner_company_id

    async def get_by_id(self, user_id: str, partner_id: str) -> SimpleNamespace | None:
        await sleep(0)
        if self.partner_company_id is None:
            return None
        return SimpleNamespace(id=partner_id, company_id=self.partner_company_id)


class ExpenseCompanyScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_expense_requires_company_ownership(self) -> None:
        service = ExpenseService(_FakeExpenseRepo(), _FailingCompanyService(), _FakePartnerRepo(None))

        with self.assertRaises(HTTPException) as raised:
            await service.create_expense(
                "user-1",
                ExpenseCreate(
                    company_id="company-1",
                    counterparty="Office Store",
                    expense_date=date(2026, 4, 27),
                    amount=Decimal("10.00"),
                    currency="EUR",
                    category="office",
                ),
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail, "Company not found")

    async def test_create_expense_rejects_partner_from_other_company(self) -> None:
        service = ExpenseService(
            _FakeExpenseRepo(),
            _FakeCompanyService(),
            _FakePartnerRepo(partner_company_id="company-2"),
        )

        with self.assertRaises(HTTPException) as raised:
            await service.create_expense(
                "user-1",
                ExpenseCreate(
                    company_id="company-1",
                    partner_id="partner-1",
                    counterparty="Office Store",
                    expense_date=date(2026, 4, 27),
                    amount=Decimal("10.00"),
                    currency="EUR",
                    category="office",
                ),
            )

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail, "Partner not found")

    async def test_list_expenses_filters_by_company(self) -> None:
        repo = _FakeExpenseRepo()
        company_service = _FakeCompanyService()
        service = ExpenseService(repo, company_service, _FakePartnerRepo(None))

        envelope = await service.list_expenses_envelope(
            "user-1",
            ExpenseFilters(company_id="company-1"),
            limit=10,
            offset=0,
        )

        self.assertEqual(company_service.required_company_id, "company-1")
        self.assertIsNotNone(repo.last_list_filters)
        self.assertEqual(repo.last_list_filters.company_id, "company-1")
        self.assertEqual(envelope.total_count, 1)
        self.assertEqual(envelope.items[0].company_id, "company-1")


if __name__ == "__main__":
    unittest.main()
