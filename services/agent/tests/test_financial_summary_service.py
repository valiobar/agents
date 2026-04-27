from __future__ import annotations

import sys
import unittest
from asyncio import sleep
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.financial import FinancialSummaryRequest
from app.services.financial_summary_service import FinancialSummaryService


class FakeInvoiceRepository:
    async def aggregate_summary(self, user_id: str, request: FinancialSummaryRequest) -> list[dict]:
        await sleep(0)
        return [
            {
                "key": "all",
                "currency": "EUR",
                "invoice_total": Decimal("80131.73"),
            },
            {
                "key": "all",
                "currency": "BGN",
                "invoice_total": Decimal("100.00"),
            },
        ]


class FakeExpenseRepository:
    async def aggregate_summary(self, user_id: str, request: FinancialSummaryRequest) -> list[dict]:
        await sleep(0)
        return [
            {
                "key": "all",
                "currency": "EUR",
                "expense_total": Decimal("10.00"),
                "deductible_expense_total": Decimal("5.00"),
            }
        ]


class FinancialSummaryServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_summary_converts_eur_to_bgn_and_keeps_raw_currency_totals(self) -> None:
        service = FinancialSummaryService(FakeInvoiceRepository(), FakeExpenseRepository())

        summary = await service.get_summary("user-1", FinancialSummaryRequest())

        self.assertEqual(summary.currency, "BGN")
        self.assertEqual(summary.exchange_rates_to_bgn["EUR"], Decimal("1.95583000"))
        self.assertEqual(summary.invoice_total, Decimal("156824.04"))
        self.assertEqual(summary.expense_total, Decimal("19.56"))
        self.assertEqual(summary.deductible_expense_total, Decimal("9.78"))
        self.assertEqual(summary.net_total, Decimal("156804.48"))
        self.assertEqual(summary.unsupported_currencies, [])

        raw_totals = {item.currency: item for item in summary.totals_by_currency}
        self.assertEqual(raw_totals["EUR"].invoice_total, Decimal("80131.73"))
        self.assertEqual(raw_totals["EUR"].expense_total, Decimal("10.00"))
        self.assertEqual(raw_totals["BGN"].invoice_total, Decimal("100.00"))

        self.assertEqual(summary.buckets[0].invoice_total, Decimal("156824.04"))
        self.assertEqual(summary.buckets[0].totals_by_currency[1].currency, "EUR")


if __name__ == "__main__":
    unittest.main()
