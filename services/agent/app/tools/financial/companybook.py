from __future__ import annotations

import json

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.clients.business import BusinessClientError
from app.models.financial.companybook import CompanyBookPartnerMappingError
from app.models.financial.partner import PartnerCreate, PartnerKind, PartnerResponse
from app.runtime.tool_context import ToolContext
from app.services.companybook_service import CompanyBookError
from app.tools.financial.operations import _with_scoped_company


class SearchCompanyBookArgs(BaseModel):
    name: str = Field(
        min_length=3,
        max_length=200,
        description="Company name or UIC to search in CompanyBook.BG.",
    )
    limit: int = Field(default=5, ge=1, le=10)
    active_only: bool = True


class ImportCompanyBookPartnerArgs(BaseModel):
    company_id: str | None = Field(
        default=None,
        max_length=64,
        description="Required when the agent is not assigned to one company.",
    )
    uic: str = Field(
        min_length=5,
        max_length=32,
        description="UIC of the selected CompanyBook company.",
    )
    kind: PartnerKind = "client"


def _json(data: object) -> str:
    return json.dumps(data, default=str, ensure_ascii=False)


def _matches_registration_number(partner: PartnerResponse, registration_number: str) -> bool:
    return partner.registration_number.strip().casefold() == registration_number.strip().casefold()


async def _resolve_existing_partner_by_uic(
    user_id: str,
    company_id: str,
    uic: str,
    context: ToolContext,
) -> PartnerResponse | None:
    matches = await context.business_client.list_partners(
        user_id=user_id,
        company_id=company_id,
        kind=None,
        query=uic,
        limit=20,
        offset=0,
    )
    exact_matches = [partner for partner in matches if _matches_registration_number(partner, uic)]
    return exact_matches[0] if len(exact_matches) == 1 else None


async def _create_or_resolve_partner(
    user_id: str,
    company_id: str,
    payload: PartnerCreate,
    context: ToolContext,
) -> PartnerResponse | str:
    try:
        return await context.business_client.create_partner(user_id, payload)
    except BusinessClientError as exc:
        if exc.status_code != 409:
            return exc.message
        try:
            existing = await _resolve_existing_partner_by_uic(
                user_id=user_id,
                company_id=company_id,
                uic=payload.registration_number,
                context=context,
            )
        except BusinessClientError as resolve_exc:
            return resolve_exc.message
        if existing is not None:
            return existing
        return _json(
            {
                "message": (
                    "Partner already exists for this UIC, but it could not "
                    "be resolved automatically. Ask the user to search local partners."
                ),
                "uic": payload.registration_number,
            }
        )


async def _import_companybook_partner_for_company(
    user_id: str,
    company_id: str,
    args: ImportCompanyBookPartnerArgs,
    context: ToolContext,
) -> str:
    try:
        existing = await _resolve_existing_partner_by_uic(
            user_id=user_id,
            company_id=company_id,
            uic=args.uic,
            context=context,
        )
    except BusinessClientError as exc:
        return exc.message
    if existing is not None:
        return _json(existing.model_dump(mode="json"))

    try:
        detail = await context.companybook_service.get_company(args.uic)
        payload = detail.to_partner_create(company_id=company_id, kind=args.kind)
    except CompanyBookPartnerMappingError as exc:
        return _json(
            {
                "message": str(exc),
                "missing_fields": exc.missing_fields,
                "partner_draft": exc.partner_draft,
            }
        )
    except CompanyBookError as exc:
        return exc.user_message

    partner = await _create_or_resolve_partner(
        user_id=user_id,
        company_id=company_id,
        payload=payload,
        context=context,
    )
    if isinstance(partner, str):
        return partner
    return _json(partner.model_dump(mode="json"))


def build_companybook_tools(
    user_id: str,
    company_id: str | None,
    context: ToolContext,
) -> list[StructuredTool]:
    async def search_companybook_companies(**kwargs) -> str:
        args = SearchCompanyBookArgs.model_validate(kwargs)
        try:
            response = await context.companybook_service.search_companies(
                name=args.name,
                limit=args.limit,
                active_only=args.active_only,
            )
        except CompanyBookError as exc:
            return exc.user_message

        return _json(
            {
                "results": [result.model_dump(mode="json") for result in response.results],
                "total": response.total,
            }
        )

    async def import_companybook_partner(**kwargs) -> str:
        args = ImportCompanyBookPartnerArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            return await _import_companybook_partner_for_company(
                user_id=user_id,
                company_id=target_company_id,
                args=args,
                context=context,
            )

        return await _with_scoped_company(
            company_id,
            args.company_id,
            "importing CompanyBook partner",
            run,
        )

    return [
        StructuredTool.from_function(
            coroutine=search_companybook_companies,
            name="search_companybook_companies",
            description=(
                "Search CompanyBook.BG for Bulgarian companies by partial name or UIC. "
                "Use this only after searching local partners or when the user asks to search the registry."
            ),
            args_schema=SearchCompanyBookArgs,
        ),
        StructuredTool.from_function(
            coroutine=import_companybook_partner,
            name="import_companybook_partner",
            description=(
                "Import the selected CompanyBook.BG company UIC as a partner in the current company scope. "
                "Call this before invoice creation when the invoice recipient is missing locally."
            ),
            args_schema=ImportCompanyBookPartnerArgs,
        ),
    ]
