from __future__ import annotations

from datetime import UTC, date, datetime
import json

from langchain_core.tools import StructuredTool
from pydantic import ConfigDict, Field

from app.clients.business import BusinessClientError
from app.models.financial import (
    ExpenseCreate,
    ExpenseFilters,
    FinancialSummaryRequest,
    InvoiceCreate,
    InvoiceFilters,
)
from app.runtime.tool_context import ToolContext
from app.tools.financial.company_scope import _scoped_company_id, _with_scoped_company

_UNASSIGNED_COMPANY_DESCRIPTION = (
    "Required when the agent is not assigned to one company. "
    "When the agent is assigned, the tool uses that company_id automatically."
)


def _today() -> date:
    return datetime.now(UTC).date()


def _first_day_next_month() -> date:
    today = _today()
    if today.month == 12:
        return date(today.year + 1, 1, 1)
    return date(today.year, today.month + 1, 1)


class QueryInvoicesArgs(InvoiceFilters):
    model_config = ConfigDict(extra="forbid")
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0, le=10_000)


class QueryExpensesArgs(ExpenseFilters):
    model_config = ConfigDict(extra="forbid")
    company_id: str | None = Field(default=None, description=_UNASSIGNED_COMPANY_DESCRIPTION)
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0, le=10_000)


class CreateInvoiceArgs(InvoiceCreate):
    model_config = ConfigDict(extra="forbid")
    issue_date: date = Field(default_factory=_today, description="Defaults to today in UTC.")
    tax_event_date: date = Field(default_factory=_today, description="Defaults to today in UTC.")
    due_date: date | None = Field(
        default_factory=_first_day_next_month,
        description="Defaults to the first day of next month in UTC.",
    )
    company_id: str | None = Field(
        default=None,
        description=(
            "Required when the agent is not assigned to one company. "
            "When the agent is assigned, the tool uses that company_id automatically."
        ),
    )
    partner_id: str | None = Field(
        default=None,
        max_length=64,
        description=(
            "Prefer the partner id returned by resolve_partner_by_name. "
            "Exact partner registration numbers or names are accepted as a fallback."
        ),
    )
    confirmed: bool = Field(
        default=False,
        description="Must be true only after the user explicitly confirms creation.",
    )


class RecordExpenseArgs(ExpenseCreate):
    model_config = ConfigDict(extra="forbid")
    company_id: str | None = Field(default=None, description=_UNASSIGNED_COMPANY_DESCRIPTION)
    confirmed: bool = Field(
        default=False,
        description="Must be true only after the user explicitly confirms recording the expense.",
    )


class GetFinancialSummaryArgs(FinancialSummaryRequest):
    model_config = ConfigDict(extra="forbid")


def _json(data: object) -> str:
    return json.dumps(data, default=str, ensure_ascii=False)


def build_financial_tools(user_id: str, company_id: str | None, context: ToolContext) -> list[StructuredTool]:
    async def query_invoices(**kwargs) -> str:
        args = QueryInvoicesArgs.model_validate(kwargs)
        filters_data = args.model_dump(exclude={"limit", "offset"})
        target_company_id, scope_error = _scoped_company_id(company_id, filters_data.get("company_id"), "querying invoices")
        if scope_error:
            return scope_error
        if target_company_id is not None:
            filters_data["company_id"] = target_company_id
        filters = InvoiceFilters.model_validate(filters_data)
        try:
            invoices = await context.business_client.list_invoices(
                user_id,
                filters,
                limit=args.limit,
                offset=args.offset,
            )
        except BusinessClientError as exc:
            return exc.message
        return _json(invoices.model_dump(mode="json"))

    async def query_expenses(**kwargs) -> str:
        args = QueryExpensesArgs.model_validate(kwargs)
        async def run(target_company_id: str) -> str:
            filters_data = args.model_dump(exclude={"limit", "offset"})
            filters_data["company_id"] = target_company_id
            filters = ExpenseFilters.model_validate(filters_data)
            try:
                expenses = await context.business_client.list_expenses(
                    user_id,
                    filters,
                    limit=args.limit,
                    offset=args.offset,
                )
            except BusinessClientError as exc:
                return exc.message
            return _json(expenses.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "querying expenses", run)

    async def get_financial_summary(**kwargs) -> str:
        request_data = GetFinancialSummaryArgs.model_validate(kwargs).model_dump()
        target_company_id, scope_error = _scoped_company_id(
            company_id,
            request_data.get("company_id"),
            "summarizing financial data",
        )
        if scope_error:
            return scope_error
        if target_company_id is not None:
            request_data["company_id"] = target_company_id
        request = FinancialSummaryRequest.model_validate(request_data)
        try:
            summary = await context.business_client.get_financial_summary(user_id, request)
        except BusinessClientError as exc:
            return exc.message
        return _json(summary.model_dump(mode="json"))

    async def create_invoice(**kwargs) -> str:
        args = CreateInvoiceArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            payload_data = args.model_dump(exclude={"confirmed"})
            payload_data["company_id"] = target_company_id
            payload = InvoiceCreate.model_validate(payload_data)
            if not args.confirmed:
                return _json(
                    {
                        "message": "Confirmation required before creating this invoice. Present this draft and ask the user to confirm.",
                        "invoice_draft": payload.model_dump(mode="json"),
                    }
                )
            try:
                invoice = await context.business_client.create_invoice(user_id, payload)
            except BusinessClientError as exc:
                return exc.message
            return _json(invoice.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "creating invoices", run)

    async def record_expense(**kwargs) -> str:
        args = RecordExpenseArgs.model_validate(kwargs)
        async def run(target_company_id: str) -> str:
            payload_data = args.model_dump(exclude={"confirmed"})
            payload_data["company_id"] = target_company_id
            payload = ExpenseCreate.model_validate(payload_data)
            if not args.confirmed:
                return _json(
                    {
                        "message": "Confirmation required before recording this expense. Present this draft and ask the user to confirm.",
                        "expense_draft": payload.model_dump(mode="json"),
                    }
                )
            try:
                expense = await context.business_client.create_expense(user_id, payload)
            except BusinessClientError as exc:
                return exc.message
            return _json(expense.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "recording expenses", run)

    return [
        StructuredTool.from_function(
            coroutine=query_invoices,
            name="query_invoices",
            description="Query invoices by status, dates, partner, amount, or category. Defaults to the agent's current company when assigned.",
            args_schema=QueryInvoicesArgs,
        ),
        StructuredTool.from_function(
            coroutine=query_expenses,
            name="query_expenses",
            description="Query the user's expenses by category, dates, counterparty, amount, or deductibility.",
            args_schema=QueryExpensesArgs,
        ),
        StructuredTool.from_function(
            coroutine=get_financial_summary,
            name="get_financial_summary",
            description=(
                "Summarize invoice and expense totals, optionally grouped by category, counterparty, or month. "
                "Use raw totals_by_currency for ordinary reporting in source currencies. The response also "
                "includes EUR-denominated top-level totals for cross-currency comparison; use source totals "
                "when users explicitly ask for native currency amounts."
            ),
            args_schema=GetFinancialSummaryArgs,
        ),
        StructuredTool.from_function(
            coroutine=create_invoice,
            name="create_invoice",
            description=(
                "Create an invoice within one resolved company scope only after explicit user confirmation. "
                "Before creating, search and resolve the partner (client) or create the partner first."
            ),
            args_schema=CreateInvoiceArgs,
        ),
        StructuredTool.from_function(
            coroutine=record_expense,
            name="record_expense",
            description="Record an expense only after explicit user confirmation.",
            args_schema=RecordExpenseArgs,
        ),
    ]
