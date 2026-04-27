from __future__ import annotations

from decimal import Decimal

from app.models.financial import (
    FinancialSummaryBucket,
    FinancialSummaryCurrencyTotals,
    FinancialSummaryRequest,
    FinancialSummaryResponse,
)
from app.repositories.financial_utils import EXCHANGE_RATES_TO_BGN, convert_to_bgn, quantize_money
from app.repositories.expense_repo import ExpenseRepository
from app.repositories.invoice_repo import InvoiceRepository


class FinancialSummaryService:
    def __init__(self, invoice_repo: InvoiceRepository, expense_repo: ExpenseRepository) -> None:
        self.invoice_repo = invoice_repo
        self.expense_repo = expense_repo

    def _currency_totals(self, values: dict[str, FinancialSummaryCurrencyTotals]) -> list[FinancialSummaryCurrencyTotals]:
        return sorted(values.values(), key=lambda item: item.currency)

    def _add_invoice_amount(
        self,
        totals_by_currency: dict[str, FinancialSummaryCurrencyTotals],
        buckets: dict[str, FinancialSummaryBucket],
        bucket_currency_totals: dict[str, dict[str, FinancialSummaryCurrencyTotals]],
        key: str,
        currency: str,
        amount: Decimal,
    ) -> Decimal | None:
        total = totals_by_currency.setdefault(currency, FinancialSummaryCurrencyTotals(currency=currency))
        total.invoice_total += amount
        total.net_total += amount

        bucket_total = bucket_currency_totals.setdefault(key, {}).setdefault(
            currency,
            FinancialSummaryCurrencyTotals(currency=currency),
        )
        bucket_total.invoice_total += amount
        bucket_total.net_total += amount

        converted = convert_to_bgn(amount, currency)
        if converted is not None:
            buckets.setdefault(key, FinancialSummaryBucket(key=key)).invoice_total += converted
        return converted

    def _add_expense_amount(
        self,
        totals_by_currency: dict[str, FinancialSummaryCurrencyTotals],
        buckets: dict[str, FinancialSummaryBucket],
        bucket_currency_totals: dict[str, dict[str, FinancialSummaryCurrencyTotals]],
        key: str,
        currency: str,
        amount: Decimal,
        deductible: Decimal,
    ) -> tuple[Decimal | None, Decimal | None]:
        total = totals_by_currency.setdefault(currency, FinancialSummaryCurrencyTotals(currency=currency))
        total.expense_total += amount
        total.deductible_expense_total += deductible
        total.net_total -= amount

        bucket_total = bucket_currency_totals.setdefault(key, {}).setdefault(
            currency,
            FinancialSummaryCurrencyTotals(currency=currency),
        )
        bucket_total.expense_total += amount
        bucket_total.deductible_expense_total += deductible
        bucket_total.net_total -= amount

        converted_amount = convert_to_bgn(amount, currency)
        converted_deductible = convert_to_bgn(deductible, currency)
        if converted_amount is not None and converted_deductible is not None:
            bucket = buckets.setdefault(key, FinancialSummaryBucket(key=key))
            bucket.expense_total += converted_amount
            bucket.deductible_expense_total += converted_deductible
        return converted_amount, converted_deductible

    async def _collect_invoice_totals(
        self,
        user_id: str,
        request: FinancialSummaryRequest,
        totals_by_currency: dict[str, FinancialSummaryCurrencyTotals],
        buckets: dict[str, FinancialSummaryBucket],
        bucket_currency_totals: dict[str, dict[str, FinancialSummaryCurrencyTotals]],
        unsupported_currencies: set[str],
    ) -> Decimal:
        invoice_total = Decimal("0")
        for row in await self.invoice_repo.aggregate_summary(user_id, request):
            key = str(row.get("key") or row.get("_id") or "all")
            currency = str(row.get("currency") or "BGN")
            amount = row.get("invoice_total") or Decimal("0")
            converted = self._add_invoice_amount(
                totals_by_currency,
                buckets,
                bucket_currency_totals,
                key,
                currency,
                amount,
            )
            if converted is None:
                unsupported_currencies.add(currency)
            else:
                invoice_total += converted
        return invoice_total

    async def _collect_expense_totals(
        self,
        user_id: str,
        request: FinancialSummaryRequest,
        totals_by_currency: dict[str, FinancialSummaryCurrencyTotals],
        buckets: dict[str, FinancialSummaryBucket],
        bucket_currency_totals: dict[str, dict[str, FinancialSummaryCurrencyTotals]],
        unsupported_currencies: set[str],
    ) -> tuple[Decimal, Decimal]:
        expense_total = Decimal("0")
        deductible_total = Decimal("0")
        for row in await self.expense_repo.aggregate_summary(user_id, request):
            key = str(row.get("key") or row.get("_id") or "all")
            currency = str(row.get("currency") or "BGN")
            amount = row.get("expense_total") or Decimal("0")
            deductible = row.get("deductible_expense_total") or Decimal("0")
            converted_amount, converted_deductible = self._add_expense_amount(
                totals_by_currency,
                buckets,
                bucket_currency_totals,
                key,
                currency,
                amount,
                deductible,
            )
            if converted_amount is None or converted_deductible is None:
                unsupported_currencies.add(currency)
            else:
                expense_total += converted_amount
                deductible_total += converted_deductible
        return expense_total, deductible_total

    async def get_summary(self, user_id: str, request: FinancialSummaryRequest) -> FinancialSummaryResponse:
        buckets: dict[str, FinancialSummaryBucket] = {}
        totals_by_currency: dict[str, FinancialSummaryCurrencyTotals] = {}
        bucket_currency_totals: dict[str, dict[str, FinancialSummaryCurrencyTotals]] = {}
        invoice_total = Decimal("0")
        expense_total = Decimal("0")
        deductible_total = Decimal("0")
        unsupported_currencies: set[str] = set()

        if request.include_invoices:
            invoice_total = await self._collect_invoice_totals(
                user_id,
                request,
                totals_by_currency,
                buckets,
                bucket_currency_totals,
                unsupported_currencies,
            )

        if request.include_expenses:
            expense_total, deductible_total = await self._collect_expense_totals(
                user_id,
                request,
                totals_by_currency,
                buckets,
                bucket_currency_totals,
                unsupported_currencies,
            )

        for key, bucket in buckets.items():
            bucket.invoice_total = quantize_money(bucket.invoice_total)
            bucket.expense_total = quantize_money(bucket.expense_total)
            bucket.deductible_expense_total = quantize_money(bucket.deductible_expense_total)
            bucket.totals_by_currency = self._currency_totals(bucket_currency_totals.get(key, {}))

        return FinancialSummaryResponse(
            currency="BGN",
            exchange_rates_to_bgn=EXCHANGE_RATES_TO_BGN,
            invoice_total=quantize_money(invoice_total),
            expense_total=quantize_money(expense_total),
            deductible_expense_total=quantize_money(deductible_total),
            net_total=quantize_money(invoice_total - expense_total),
            buckets=sorted(buckets.values(), key=lambda item: item.key),
            totals_by_currency=self._currency_totals(totals_by_currency),
            unsupported_currencies=sorted(unsupported_currencies),
        )

