from __future__ import annotations

import json

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, field_validator

from app.clients.business import BusinessClientError
from app.models.financial.partner import PartnerCreate, PartnerKind, PartnerResponse
from app.runtime.tool_context import ToolContext
from app.tools.financial.company_scope import _with_scoped_company

_UNASSIGNED_COMPANY_DESCRIPTION = "Required when the agent is not assigned to one company."


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


def _json(data: object) -> str:
    return json.dumps(data, default=str, ensure_ascii=False)


def _matches_registration_number(partner: PartnerResponse, registration_number: str) -> bool:
    return partner.registration_number.strip().casefold() == registration_number.strip().casefold()


async def _resolve_existing_partner_by_registration_number(
    user_id: str,
    company_id: str,
    registration_number: str,
    context: ToolContext,
) -> PartnerResponse | None:
    matches = await context.business_client.list_partners(
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
) -> PartnerResponse | str:
    try:
        return await context.business_client.create_partner(user_id, payload)
    except BusinessClientError as exc:
        if exc.status_code != 409:
            return exc.message
        try:
            existing = await _resolve_existing_partner_by_registration_number(
                user_id=user_id,
                company_id=company_id,
                registration_number=payload.registration_number,
                context=context,
            )
        except BusinessClientError as resolve_exc:
            return resolve_exc.message
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


def build_partner_tools(
    user_id: str,
    company_id: str | None,
    context: ToolContext,
) -> list[StructuredTool]:
    async def search_partners(**kwargs) -> str:
        args = SearchPartnersArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            try:
                partners = await context.business_client.list_partners(
                    user_id=user_id,
                    company_id=target_company_id,
                    kind=args.kind,
                    query=args.query,
                    limit=args.limit,
                    offset=0,
                )
            except BusinessClientError as exc:
                return exc.message
            return _json([partner.model_dump(mode="json") for partner in partners])

        return await _with_scoped_company(company_id, args.company_id, "searching partners", run)

    async def resolve_partner_by_name(**kwargs) -> str:
        args = ResolvePartnerArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            try:
                partners = await context.business_client.list_partners(
                    user_id=user_id,
                    company_id=target_company_id,
                    kind=args.kind,
                    query=args.name,
                    limit=args.max_matches,
                    offset=0,
                )
            except BusinessClientError as exc:
                return exc.message
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
            try:
                partner = await context.business_client.get_partner(
                    user_id=user_id,
                    company_id=target_company_id,
                    partner_id=args.partner_id,
                )
            except BusinessClientError as exc:
                return exc.message
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
