from __future__ import annotations

import sys
import unittest
from asyncio import sleep
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.common.models import ListEnvelope, make_list_envelope
from app.dependencies import get_expense_service
from app.main import app
from app.financial.models import ExpenseCreate, ExpenseFilters, ExpenseInDB


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FakeExpenseService:
    def __init__(self) -> None:
        self.created: ExpenseInDB | None = None

    async def create_expense(self, user_id: str, payload: ExpenseCreate) -> ExpenseInDB:
        await sleep(0)
        now = _now()
        self.created = ExpenseInDB(
            id="expense-1",
            user_id=user_id,
            company_id=payload.company_id,
            partner_id=payload.partner_id,
            counterparty=payload.counterparty,
            expense_date=payload.expense_date,
            amount=payload.amount or Decimal("1.00"),
            currency=payload.currency,
            category=payload.category,
            description=payload.description,
            deductible=payload.deductible,
            deductible_rate=payload.deductible_rate,
            source_document_type=payload.source_document_type,
            source_document_id=payload.source_document_id,
            source_document_number=payload.source_document_number,
            items=None,
            deductible_amount=payload.amount or Decimal("1.00"),
            created_at=now,
            updated_at=now,
        )
        return self.created

    async def list_expenses(self, user_id: str, filters: ExpenseFilters, limit: int, offset: int) -> list[ExpenseInDB]:
        await sleep(0)
        return [self.created] if self.created else []

    async def list_expenses_envelope(
        self, user_id: str, filters: ExpenseFilters, limit: int, offset: int
    ) -> ListEnvelope[ExpenseInDB]:
        await sleep(0)
        items = [self.created] if self.created else []
        return make_list_envelope(items=items, total_count=len(items), offset=offset, limit=limit)

    async def get_expense(self, user_id: str, expense_id: str) -> ExpenseInDB:
        await sleep(0)
        assert self.created is not None
        return self.created


class ExpenseRouteContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.expense_service = FakeExpenseService()
        app.dependency_overrides[get_expense_service] = lambda: self.expense_service
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_create_list_get_preserve_source_document_number(self) -> None:
        headers = {"x-user-id": "user-1"}
        create_response = self.client.post(
            "/expenses",
            headers=headers,
            json={
                "company_id": "company-1",
                "counterparty": "Office Store",
                "expense_date": "2026-04-27",
                "amount": "24.00",
                "category": "office",
                "source_document_type": "receipt",
                "source_document_id": "doc-1",
                "source_document_number": "R-839201",
            },
        )
        self.assertEqual(create_response.status_code, 201)
        self.assertEqual(create_response.json()["source_document_number"], "R-839201")

        list_response = self.client.get("/expenses?company_id=company-1&limit=10", headers=headers)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["items"][0]["source_document_number"], "R-839201")

        get_response = self.client.get("/expenses/expense-1", headers=headers)
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["source_document_number"], "R-839201")


if __name__ == "__main__":
    unittest.main()

