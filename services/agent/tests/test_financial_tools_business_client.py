from __future__ import annotations

import json
import sys
import unittest
from asyncio import sleep
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.financial import (
    ExpenseCreate,
    ExpenseFilters,
    ExpenseItem,
    ExpenseListResponse,
    ExpenseResponse,
    FinancialSummaryRequest,
    FinancialSummaryResponse,
    InvoiceCreate,
    InvoiceResponse,
)
from app.tools.financial import build_financial_tools


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _expense_response() -> ExpenseResponse:
    item = ExpenseItem(
        description="Paper",
        quantity=Decimal("2"),
        unit_price=Decimal("5.00"),
        category="office",
        total=Decimal("10.00"),
    )
    return ExpenseResponse(
        id="expense-1",
        user_id="user-1",
        company_id="company-1",
        partner_id=None,
        counterparty="Office Store",
        expense_date=date(2026, 4, 27),
        amount=Decimal("10.00"),
        currency="EUR",
        category="office",
        description="Office supplies",
        deductible=True,
        deductible_rate=Decimal("1.0"),
        source_document_type="receipt",
        source_document_id=None,
        items=[item],
        deductible_amount=Decimal("10.00"),
        created_at=_now(),
        updated_at=_now(),
    )


class FakeBusinessClient:
    def __init__(self) -> None:
        self.create_expense_calls = 0
        self.create_invoice_calls = 0
        self.last_expense_offset: int | None = None
        self.last_expense_filters: ExpenseFilters | None = None
        self.last_created_expense_payload: ExpenseCreate | None = None

    async def list_expenses(
        self,
        user_id: str,
        filters: ExpenseFilters,
        *,
        limit: int,
        offset: int,
    ) -> ExpenseListResponse:
        await sleep(0)
        self.last_expense_offset = offset
        self.last_expense_filters = filters
        item = _expense_response()
        return ExpenseListResponse(
            total_count=1,
            returned_count=1,
            offset=offset,
            limit=limit,
            truncated=False,
            next_offset=None,
            items=[item],
        )

    async def create_expense(self, user_id: str, payload: ExpenseCreate) -> ExpenseResponse:
        await sleep(0)
        self.create_expense_calls += 1
        self.last_created_expense_payload = payload
        return _expense_response()

    async def create_invoice(self, user_id: str, payload: InvoiceCreate) -> InvoiceResponse:
        await sleep(0)
        self.create_invoice_calls += 1
        raise AssertionError("create_invoice should not be called without confirmation")

    async def get_financial_summary(
        self,
        user_id: str,
        request: FinancialSummaryRequest,
    ) -> FinancialSummaryResponse:
        await sleep(0)
        return FinancialSummaryResponse(
            currency="EUR",
            exchange_rates_to_eur={"BGN": Decimal("0.5113"), "EUR": Decimal("1")},
            invoice_total=Decimal("80192.25"),
            expense_total=Decimal("10.00"),
            deductible_expense_total=Decimal("5.00"),
            net_total=Decimal("80182.25"),
            buckets=[],
            totals_by_currency=[],
            unsupported_currencies=[],
        )


class FinancialToolsBusinessClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_query_expenses_serializes_business_response_shape(self) -> None:
        business_client = FakeBusinessClient()
        context = SimpleNamespace(business_client=business_client)
        tool = next(
            tool
            for tool in build_financial_tools("user-1", "company-1", context)
            if tool.name == "query_expenses"
        )

        result = await tool.ainvoke({"company_id": "company-1", "limit": 1, "offset": 7})
        payload = json.loads(result)

        self.assertEqual(payload["total_count"], 1)
        self.assertEqual(payload["offset"], 7)
        self.assertEqual(payload["items"][0]["id"], "expense-1")
        self.assertEqual(payload["items"][0]["amount"], "10.00")
        self.assertEqual(payload["items"][0]["deductible_amount"], "10.00")
        self.assertEqual(business_client.last_expense_offset, 7)
        self.assertIsNotNone(business_client.last_expense_filters)
        self.assertEqual(business_client.last_expense_filters.company_id, "company-1")

    async def test_query_expenses_uses_assigned_company_scope_when_company_not_passed(self) -> None:
        business_client = FakeBusinessClient()
        context = SimpleNamespace(business_client=business_client)
        tool = next(
            tool
            for tool in build_financial_tools("user-1", "company-1", context)
            if tool.name == "query_expenses"
        )

        await tool.ainvoke({"limit": 5, "offset": 0})

        self.assertIsNotNone(business_client.last_expense_filters)
        self.assertEqual(business_client.last_expense_filters.company_id, "company-1")

    async def test_query_expenses_rejects_mismatched_company_for_assigned_agent(self) -> None:
        business_client = FakeBusinessClient()
        context = SimpleNamespace(business_client=business_client)
        tool = next(
            tool
            for tool in build_financial_tools("user-1", "company-1", context)
            if tool.name == "query_expenses"
        )

        result = await tool.ainvoke({"company_id": "company-2", "limit": 5, "offset": 0})

        self.assertIn("cannot use company_id 'company-2' for querying expenses", result)

    async def test_query_expenses_requires_company_for_unassigned_agent(self) -> None:
        business_client = FakeBusinessClient()
        context = SimpleNamespace(business_client=business_client)
        tool = next(
            tool
            for tool in build_financial_tools("user-1", None, context)
            if tool.name == "query_expenses"
        )

        result = await tool.ainvoke({"limit": 5, "offset": 0})

        self.assertIn("Choose a company before querying expenses", result)

    async def test_get_financial_summary_serializes_business_response_shape(self) -> None:
        business_client = FakeBusinessClient()
        context = SimpleNamespace(business_client=business_client)
        tool = next(
            tool
            for tool in build_financial_tools("user-1", "company-1", context)
            if tool.name == "get_financial_summary"
        )

        result = await tool.ainvoke({"include_invoices": True, "include_expenses": True})
        payload = json.loads(result)

        self.assertEqual(payload["currency"], "EUR")
        self.assertEqual(payload["invoice_total"], "80192.25")
        self.assertEqual(payload["exchange_rates_to_eur"]["BGN"], "0.5113")

    async def test_record_expense_requires_confirmation_before_http_call(self) -> None:
        business_client = FakeBusinessClient()
        context = SimpleNamespace(business_client=business_client)
        tool = next(
            tool
            for tool in build_financial_tools("user-1", "company-1", context)
            if tool.name == "record_expense"
        )

        result = await tool.ainvoke(
            {
                "counterparty": "Office Store",
                "company_id": "company-1",
                "expense_date": "2026-04-27",
                "amount": "10.00",
                "currency": "EUR",
                "category": "office",
                "confirmed": False,
            }
        )

        payload = json.loads(result)

        self.assertIn("Confirmation required", payload["message"])
        self.assertEqual(payload["expense_draft"]["company_id"], "company-1")
        self.assertEqual(business_client.create_expense_calls, 0)

    async def test_record_expense_requires_company_for_unassigned_agent(self) -> None:
        business_client = FakeBusinessClient()
        context = SimpleNamespace(business_client=business_client)
        tool = next(
            tool
            for tool in build_financial_tools("user-1", None, context)
            if tool.name == "record_expense"
        )

        result = await tool.ainvoke(
            {
                "counterparty": "Office Store",
                "expense_date": "2026-04-27",
                "amount": "10.00",
                "currency": "EUR",
                "category": "office",
                "confirmed": False,
            }
        )

        self.assertIn("Choose a company before recording expenses", result)
        self.assertEqual(business_client.create_expense_calls, 0)

    async def test_record_expense_uses_assigned_company_scope(self) -> None:
        business_client = FakeBusinessClient()
        context = SimpleNamespace(business_client=business_client)
        tool = next(
            tool
            for tool in build_financial_tools("user-1", "company-1", context)
            if tool.name == "record_expense"
        )

        result = await tool.ainvoke(
            {
                "counterparty": "Office Store",
                "expense_date": "2026-04-27",
                "amount": "10.00",
                "currency": "EUR",
                "category": "office",
                "confirmed": True,
            }
        )

        payload = json.loads(result)
        self.assertEqual(payload["id"], "expense-1")
        self.assertEqual(business_client.create_expense_calls, 1)
        self.assertIsNotNone(business_client.last_created_expense_payload)
        self.assertEqual(business_client.last_created_expense_payload.company_id, "company-1")

    async def test_create_invoice_requires_confirmation_before_http_call(self) -> None:
        business_client = FakeBusinessClient()
        context = SimpleNamespace(business_client=business_client)
        tool = next(
            tool
            for tool in build_financial_tools("user-1", "company-1", context)
            if tool.name == "create_invoice"
        )

        result = await tool.ainvoke(
            {
                "partner_id": "partner-1",
                "issue_date": "2026-04-27",
                "tax_event_date": "2026-04-27",
                "due_date": "2026-05-11",
                "items": [
                    {
                        "description": "Accounting consultation",
                        "quantity": "1",
                        "unit_label": "pcs",
                        "unit_price": "100.00",
                        "vat_rate": "0.20",
                        "category": "services",
                    }
                ],
                "confirmed": False,
            }
        )
        payload = json.loads(result)

        self.assertIn("Confirmation required", payload["message"])
        self.assertEqual(business_client.create_invoice_calls, 0)


if __name__ == "__main__":
    unittest.main()
