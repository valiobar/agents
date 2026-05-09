from __future__ import annotations

import json

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, field_validator

from app.clients.business import BusinessClientError
from app.models.financial.company import CompanyResponse
from app.runtime.tool_context import ToolContext


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


def _json(data: object) -> str:
    return json.dumps(data, default=str, ensure_ascii=False)


def _company_payload(company: CompanyResponse) -> dict:
    return company.model_dump(mode="json", exclude={"logo_data_url"})


def _company_matches(company: CompanyResponse, query: str) -> bool:
    value = query.casefold()
    return value in company.name.casefold() or value in company.registration_number.casefold()


def build_company_tools(user_id: str, context: ToolContext) -> list[StructuredTool]:
    async def list_companies(**kwargs) -> str:
        args = ListCompaniesArgs.model_validate(kwargs)
        try:
            companies = await context.business_client.list_companies(user_id, limit=args.limit, offset=0)
        except BusinessClientError as exc:
            return exc.message
        if args.query:
            companies = [company for company in companies if _company_matches(company, args.query)]
        return _json([_company_payload(company) for company in companies])

    async def resolve_company_by_name(**kwargs) -> str:
        args = ResolveCompanyArgs.model_validate(kwargs)
        try:
            companies = await context.business_client.list_companies(user_id, limit=100, offset=0)
        except BusinessClientError as exc:
            return exc.message
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
