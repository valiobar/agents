from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
import json

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, field_validator
from pymongo.errors import DuplicateKeyError

from app.models.company import CompanyInDB
from app.models.financial import (
    ExpenseCreate,
    ExpenseFilters,
    FinancialSummaryRequest,
    InvoiceCreate,
    InvoiceFilters,
)
from app.models.partner import PartnerCreate, PartnerInDB, PartnerKind
from app.runtime.tool_context import ToolContext

_UNASSIGNED_COMPANY_DESCRIPTION = "Required when the agent is not assigned to one company."


def _today() -> date:
    return datetime.now(UTC).date()


def _first_day_next_month() -> date:
    today = _today()
    if today.month == 12:
        return date(today.year + 1, 1, 1)
    return date(today.year, today.month + 1, 1)


class QueryInvoicesArgs(InvoiceFilters):
    limit: int = Field(default=20, ge=1, le=50)


class QueryExpensesArgs(ExpenseFilters):
    limit: int = Field(default=20, ge=1, le=50)


class ListCompaniesArgs(BaseModel):
    query: str | None = Field(
        default=None,
        max_length=200,
        description="Optional company name or registration number search term.",
    )
    limit: int = Field(default=20, ge=1, le=50)

    @field_validator("query", mode="before")
    @classmethod
    def normalize_blank_query(cls, value: object) -> object | None:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


class ResolveCompanyArgs(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=200,
        description="Company name or registration number mentioned by the user.",
    )
    max_matches: int = Field(default=5, ge=1, le=10)


class CreateInvoiceArgs(InvoiceCreate):
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
    confirmed: bool = Field(
        default=False,
        description="Must be true only after the user explicitly confirms recording the expense.",
    )


def _json(data: object) -> str:
    return json.dumps(data, default=str, ensure_ascii=False)


def _company_scope_required(action: str) -> str:
    return (
        f"Choose a company before {action}. "
        "Use list_companies or resolve_company_by_name, then call this tool with company_id."
    )


def _scoped_company_id(
    assigned_company_id: str | None,
    requested_company_id: str | None,
    action: str,
) -> tuple[str | None, str | None]:
    if assigned_company_id is None:
        return requested_company_id, None
    if requested_company_id is not None and requested_company_id != assigned_company_id:
        return (
            None,
            f"This agent is scoped to one company and cannot use company_id '{requested_company_id}' for {action}. "
            "Retry without company_id so the agent uses its assigned company.",
        )
    return assigned_company_id, None


async def _with_scoped_company(
    assigned_company_id: str | None,
    requested_company_id: str | None,
    action: str,
    callback: Callable[[str], Awaitable[str]],
) -> str:
    target_company_id, scope_error = _scoped_company_id(assigned_company_id, requested_company_id, action)
    if scope_error:
        return scope_error
    if target_company_id is None:
        return _company_scope_required(action)
    return await callback(target_company_id)


def _company_payload(company: CompanyInDB) -> dict:
    return company.model_dump(mode="json", exclude={"logo_data_url"})


def _company_matches(company: CompanyInDB, query: str) -> bool:
    value = query.casefold()
    return value in company.name.casefold() or value in company.registration_number.casefold()


def _matches_registration_number(partner: PartnerInDB, registration_number: str) -> bool:
    return partner.registration_number.strip().casefold() == registration_number.strip().casefold()


async def _resolve_existing_partner_by_registration_number(
    user_id: str,
    company_id: str,
    registration_number: str,
    context: ToolContext,
) -> PartnerInDB | None:
    matches = await context.partner_service.list_partners(
        user_id=user_id,
        company_id=company_id,
        kind=None,
        query=registration_number,
        limit=20,
        offset=0,
    )
    exact_matches = [
        partner
        for partner in matches
        if _matches_registration_number(partner, registration_number)
    ]
    return exact_matches[0] if len(exact_matches) == 1 else None


async def _create_or_resolve_partner(
    user_id: str,
    company_id: str,
    payload: PartnerCreate,
    context: ToolContext,
) -> PartnerInDB | str:
    try:
        return await context.partner_service.create_partner(user_id, payload)
    except DuplicateKeyError:
        existing = await _resolve_existing_partner_by_registration_number(
            user_id=user_id,
            company_id=company_id,
            registration_number=payload.registration_number,
            context=context,
        )
        if existing is not None:
            return existing
        return _json(
            {
                "message": (
                    "Partner already exists for this registration number, but it could not "
                    "be resolved automatically. Ask the user to search local partners."
                ),
                "registration_number": payload.registration_number,
            }
        )


def build_company_tools(user_id: str, context: ToolContext) -> list[StructuredTool]:
    async def list_companies(**kwargs) -> str:
        args = ListCompaniesArgs.model_validate(kwargs)
        companies = await context.company_service.list_companies(user_id, limit=args.limit, offset=0)
        if args.query:
            companies = [company for company in companies if _company_matches(company, args.query)]
        return _json([_company_payload(company) for company in companies])

    async def resolve_company_by_name(**kwargs) -> str:
        args = ResolveCompanyArgs.model_validate(kwargs)
        companies = await context.company_service.list_companies(user_id, limit=100, offset=0)
        exact_matches = [
            company
            for company in companies
            if company.name.casefold() == args.name.casefold()
            or company.registration_number.casefold() == args.name.casefold()
        ]
        matches = exact_matches or [company for company in companies if _company_matches(company, args.name)]
        matches = matches[: args.max_matches]

        if not matches:
            return f"No company matching '{args.name}' was found. Ask the user which company to use or create it first."
        if len(matches) == 1:
            return _json(_company_payload(matches[0]))
        return _json(
            {
                "message": "Multiple companies match this name. Ask the user which company to use.",
                "matches": [_company_payload(company) for company in matches],
            }
        )

    return [
        StructuredTool.from_function(
            coroutine=list_companies,
            name="list_companies",
            description="List or search the user's companies before using company-scoped finance tools.",
            args_schema=ListCompaniesArgs,
        ),
        StructuredTool.from_function(
            coroutine=resolve_company_by_name,
            name="resolve_company_by_name",
            description="Resolve a company name or registration number to the company_id required by finance tools.",
            args_schema=ResolveCompanyArgs,
        ),
    ]


class SearchPartnersArgs(BaseModel):
    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )
    query: str | None = Field(
        default=None,
        max_length=200,
        description="Optional search term. Omit it to list partners in the current company.",
    )
    kind: PartnerKind | None = None
    limit: int = Field(default=10, ge=1, le=20)

    @field_validator("query", mode="before")
    @classmethod
    def normalize_blank_query(cls, value: object) -> object | None:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


class ResolvePartnerArgs(BaseModel):
    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )
    name: str = Field(
        min_length=1,
        max_length=200,
        description="Partner/company name mentioned by the user, for example 'Google'.",
    )
    kind: PartnerKind | None = Field(
        default=None,
        description="Optional partner kind. Use 'client' for outgoing invoices when known.",
    )
    max_matches: int = Field(default=5, ge=1, le=10)


class GetPartnerArgs(BaseModel):
    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )
    partner_id: str = Field(min_length=1, max_length=64)


class CreatePartnerArgs(BaseModel):
    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )
    kind: PartnerKind = "client"
    name: str = Field(min_length=1, max_length=200)
    registration_number: str = Field(min_length=1, max_length=64)
    vat_number: str | None = Field(default=None, max_length=64)
    city: str = Field(min_length=1, max_length=120)
    country: str = Field(default="Bulgaria", min_length=1, max_length=120)
    address: str = Field(min_length=1, max_length=500)
    accountable_person: str = Field(min_length=1, max_length=200)
    email: str | None = None
    phone: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=1000)


def build_partner_tools(
    user_id: str,
    company_id: str | None,
    context: ToolContext,
) -> list[StructuredTool]:
    async def search_partners(**kwargs) -> str:
        args = SearchPartnersArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            partners = await context.partner_service.list_partners(
                user_id=user_id,
                company_id=target_company_id,
                kind=args.kind,
                query=args.query,
                limit=args.limit,
                offset=0,
            )
            return _json([partner.model_dump(mode="json") for partner in partners])

        return await _with_scoped_company(company_id, args.company_id, "searching partners", run)

    async def resolve_partner_by_name(**kwargs) -> str:
        args = ResolvePartnerArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            partners = await context.partner_service.list_partners(
                user_id=user_id,
                company_id=target_company_id,
                kind=args.kind,
                query=args.name,
                limit=args.max_matches,
                offset=0,
            )
            if not partners:
                return (
                    f"No partner matching '{args.name}' was found. "
                    "Ask the user for partner details or create the partner first."
                )
            if len(partners) == 1:
                return _json(partners[0].model_dump(mode="json"))
            return _json(
                {
                    "message": "Multiple partners match this name. Ask the user which partner to use.",
                    "matches": [partner.model_dump(mode="json") for partner in partners],
                }
            )

        return await _with_scoped_company(company_id, args.company_id, "resolving partners", run)

    async def get_partner(**kwargs) -> str:
        args = GetPartnerArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            partner = await context.partner_service.get_partner(
                user_id=user_id,
                company_id=target_company_id,
                partner_id=args.partner_id,
            )
            return _json(partner.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "loading partners", run)

    async def create_partner(**kwargs) -> str:
        args = CreatePartnerArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            payload = PartnerCreate.model_validate(
                args.model_dump(exclude={"company_id"}) | {"company_id": target_company_id},
            )
            partner = await _create_or_resolve_partner(user_id, target_company_id, payload, context)
            if isinstance(partner, str):
                return partner
            return _json(partner.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "creating partners", run)

    return [
        StructuredTool.from_function(
            coroutine=search_partners,
            name="search_partners",
            description="List or search partners (clients/suppliers) within the agent's current company scope.",
            args_schema=SearchPartnersArgs,
        ),
        StructuredTool.from_function(
            coroutine=resolve_partner_by_name,
            name="resolve_partner_by_name",
            description="Find the best existing partner by a company name mentioned by the user before creating an invoice.",
            args_schema=ResolvePartnerArgs,
        ),
        StructuredTool.from_function(
            coroutine=get_partner,
            name="get_partner",
            description="Load a single partner by id within the current company scope.",
            args_schema=GetPartnerArgs,
        ),
        StructuredTool.from_function(
            coroutine=create_partner,
            name="create_partner",
            description="Create a new partner within the current company scope.",
            args_schema=CreatePartnerArgs,
        ),
    ]


def build_financial_tools(user_id: str, company_id: str | None, context: ToolContext) -> list[StructuredTool]:
    async def query_invoices(**kwargs) -> str:
        args = QueryInvoicesArgs.model_validate(kwargs)
        filters_data = args.model_dump(exclude={"limit"})
        target_company_id, scope_error = _scoped_company_id(company_id, filters_data.get("company_id"), "querying invoices")
        if scope_error:
            return scope_error
        if target_company_id is not None:
            filters_data["company_id"] = target_company_id
        filters = InvoiceFilters.model_validate(filters_data)
        invoices = await context.invoice_service.list_invoices(
            user_id,
            filters,
            limit=args.limit,
            offset=0,
        )
        return _json([item.model_dump(mode="json") for item in invoices])

    async def query_expenses(**kwargs) -> str:
        args = QueryExpensesArgs.model_validate(kwargs)
        filters = ExpenseFilters.model_validate(args.model_dump(exclude={"limit"}))
        expenses = await context.expense_service.list_expenses(
            user_id,
            filters,
            limit=args.limit,
            offset=0,
        )
        return _json([item.model_dump(mode="json") for item in expenses])

    async def get_financial_summary(**kwargs) -> str:
        request_data = FinancialSummaryRequest.model_validate(kwargs).model_dump()
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
        summary = await context.summary_service.get_summary(user_id, request)
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
            invoice = await context.invoice_service.create_invoice(user_id, payload)
            return _json(invoice.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "creating invoices", run)

    async def record_expense(**kwargs) -> str:
        args = RecordExpenseArgs.model_validate(kwargs)
        if not args.confirmed:
            return (
                "Confirmation required before recording this expense. "
                "Summarize the expense and ask the user to confirm."
            )
        payload = ExpenseCreate.model_validate(args.model_dump(exclude={"confirmed"}))
        expense = await context.expense_service.create_expense(user_id, payload)
        return _json(expense.model_dump(mode="json"))

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
                "Use raw totals_by_currency for ordinary reporting. The response also includes BGN-converted "
                "top-level totals for BGN-denominated regulation or threshold checks; EUR is converted with "
                "1.00 EUR = 1.95583000 BGN."
            ),
            args_schema=FinancialSummaryRequest,
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
