from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Literal, TypedDict

from fastapi import HTTPException, status
from langgraph.graph import END, StateGraph

from app.clients.business import BusinessClient, BusinessClientError
from app.models.financial import (
    InvoiceCreate,
    InvoiceItemCreate,
    PartnerMatchCandidate,
    PartnerResolveRequest,
)
from app.models.inventory import InventorySearchMatch, InventorySearchRequest, ResolveInventoryItemRequest, StockLevel
from app.models.sales_invoice_workflow import (
    ConfirmSalesInvoiceInventoryRequest,
    ConfirmSalesInvoiceRequest,
    CreateSalesInvoiceInventoryPreviewRequest,
    ResolvedSalesInvoiceInventoryLine,
    SalesInvoiceCreatedResponse,
    SalesInvoiceInventoryReviewResponse,
    SalesInvoiceReviewResponse,
)
from app.repositories.agent_repo import AgentRepository
from app.services.workflows import map_business_client_error, require_company_scoped_agent


class SalesInvoiceWorkflowState(TypedDict, total=False):
    user_id: str
    agent_id: str
    company_id: str
    agent_repo: AgentRepository
    business_client: BusinessClient
    preview_request: CreateSalesInvoiceInventoryPreviewRequest
    inventory_confirm_request: ConfirmSalesInvoiceInventoryRequest
    invoice_confirm_request: ConfirmSalesInvoiceRequest
    partner_candidates: list[PartnerMatchCandidate]
    resolved_inventory_lines: list[ResolvedSalesInvoiceInventoryLine]
    invoice_draft: InvoiceCreate
    warnings: list[str]
    review_type: Literal[
        "sales_invoice_inventory_review",
        "sales_invoice_review",
        "sales_invoice_created",
    ]
    response: (
        SalesInvoiceInventoryReviewResponse
        | SalesInvoiceReviewResponse
        | SalesInvoiceCreatedResponse
    )


def _first_day_next_month(value: date) -> date:
    return (value.replace(day=1) + timedelta(days=32)).replace(day=1)


def _sum_available(levels: list[StockLevel]) -> Decimal | None:
    if not levels:
        return None
    return sum((level.available_quantity for level in levels), Decimal("0"))


def _default_location_id(levels: list[StockLevel]) -> str | None:
    if not levels:
        return None
    highest = max(levels, key=lambda level: level.available_quantity)
    return highest.location_id


def _unique_candidate_item_ids(candidates: list[InventorySearchMatch]) -> list[str]:
    seen: set[str] = set()
    item_ids: list[str] = []
    for candidate in candidates:
        if candidate.item_id in seen:
            continue
        seen.add(candidate.item_id)
        item_ids.append(candidate.item_id)
    return item_ids


def _top_inventory_candidates(
    *,
    exact_match: InventorySearchMatch | None,
    candidates: list[InventorySearchMatch],
    limit: int = 5,
) -> list[InventorySearchMatch]:
    by_item_id: dict[str, InventorySearchMatch] = {}
    for candidate in [*([] if exact_match is None else [exact_match]), *candidates]:
        existing = by_item_id.get(candidate.item_id)
        if existing is None or candidate.confidence > existing.confidence:
            by_item_id[candidate.item_id] = candidate

    return sorted(by_item_id.values(), key=lambda candidate: candidate.confidence, reverse=True)[:limit]


async def _stock_levels_for_candidates(
    *,
    state: SalesInvoiceWorkflowState,
    item_ids: list[str],
) -> list[StockLevel]:
    stock_levels: list[StockLevel] = []
    for item_id in item_ids:
        stock_response = await state["business_client"].get_stock_levels(
            state["user_id"],
            company_id=state["company_id"],
            item_id=item_id,
            limit=20,
        )
        stock_levels.extend(stock_response.levels)
    return stock_levels


async def _inventory_candidates_for_line(
    *,
    state: SalesInvoiceWorkflowState,
    query: str,
) -> tuple[InventorySearchMatch | None, list[InventorySearchMatch]]:
    resolved = await state["business_client"].resolve_inventory_item(
        state["user_id"],
        ResolveInventoryItemRequest(
            company_id=state["company_id"],
            query=query,
            limit=5,
        ),
    )
    searched = await state["business_client"].search_inventory(
        state["user_id"],
        InventorySearchRequest(
            company_id=state["company_id"],
            query=query,
            include_stock=True,
            min_confidence=0,
            limit=5,
        ),
    )
    return resolved.exact_match, [*resolved.candidates, *searched.matches]


def _line_warnings(
    *,
    line_index: int,
    requested_quantity: Decimal,
    selected_item_id: str | None,
    stock_levels: list[StockLevel],
) -> list[str]:
    warnings: list[str] = []
    line_number = line_index + 1

    if not selected_item_id:
        warnings.append(
            f"Line {line_number}: No high-confidence inventory match found. Please select an item manually."
        )
        return warnings

    if not stock_levels:
        warnings.append(f"Line {line_number}: Selected item has no stock levels yet.")
        return warnings

    available = _sum_available(stock_levels)
    if available is not None and available < requested_quantity:
        warnings.append(
            f"Line {line_number}: Requested quantity {requested_quantity} exceeds available stock {available}."
        )
    return warnings


def _partner_warnings(
    *,
    partner_candidates: list[PartnerMatchCandidate],
    selected_partner_id: str | None,
    recipient_selected: bool,
) -> list[str]:
    warnings: list[str] = []
    if selected_partner_id:
        return warnings

    if partner_candidates and not recipient_selected:
        warnings.append("Partner matches were found. Select a partner or provide recipient details.")
    return warnings


async def validate_scope(state: SalesInvoiceWorkflowState) -> SalesInvoiceWorkflowState:
    company_id = await require_company_scoped_agent(
        user_id=state["user_id"],
        agent_id=state["agent_id"],
        agent_repo=state["agent_repo"],
        business_client=state["business_client"],
        workflow_name="Sales invoice inventory workflow",
    )
    return {**state, "company_id": company_id}


async def resolve_partner(state: SalesInvoiceWorkflowState) -> SalesInvoiceWorkflowState:
    request = state["preview_request"]
    if not request.partner_query:
        return {**state, "partner_candidates": []}
    try:
        response = await state["business_client"].resolve_partner(
            state["user_id"],
            PartnerResolveRequest(
                company_id=state["company_id"],
                name=request.partner_query,
                kind="client",
                limit=5,
            ),
        )
    except BusinessClientError as exc:
        raise map_business_client_error(exc) from exc
    return {**state, "partner_candidates": response.candidates}


async def resolve_inventory(state: SalesInvoiceWorkflowState) -> SalesInvoiceWorkflowState:
    resolved: list[ResolvedSalesInvoiceInventoryLine] = []
    aggregate_warnings = list(state.get("warnings", []))

    for index, line in enumerate(state["preview_request"].lines):
        try:
            exact_match, candidate_matches = await _inventory_candidates_for_line(
                state=state,
                query=line.query,
            )
            selected = exact_match if exact_match and exact_match.confidence >= 0.90 else None
            selected_item_id = selected.item_id if selected else None

            candidates = _top_inventory_candidates(
                exact_match=exact_match,
                candidates=candidate_matches,
            )

            stock_levels = await _stock_levels_for_candidates(
                state=state,
                item_ids=_unique_candidate_item_ids(candidates),
            )
            selected_stock_levels = [
                level for level in stock_levels if selected_item_id and level.item_id == selected_item_id
            ]

            line_warnings = _line_warnings(
                line_index=index,
                requested_quantity=line.quantity,
                selected_item_id=selected_item_id,
                stock_levels=selected_stock_levels,
            )
            aggregate_warnings.extend(line_warnings)

            resolved.append(
                ResolvedSalesInvoiceInventoryLine(
                    line_index=index,
                    requested=line,
                    selected_item_id=selected_item_id,
                    selected_location_id=_default_location_id(selected_stock_levels),
                    candidates=candidates,
                    stock_levels=stock_levels,
                    available_quantity=_sum_available(selected_stock_levels),
                    warnings=line_warnings,
                )
            )
        except BusinessClientError as exc:
            raise map_business_client_error(exc) from exc

    return {
        **state,
        "resolved_inventory_lines": resolved,
        "warnings": aggregate_warnings,
    }


def build_inventory_review(state: SalesInvoiceWorkflowState) -> SalesInvoiceWorkflowState:
    request = state["preview_request"]
    response = SalesInvoiceInventoryReviewResponse(
        company_id=state["company_id"],
        partner_query=request.partner_query,
        recipient=request.recipient,
        partner_candidates=state.get("partner_candidates", []),
        lines=state["resolved_inventory_lines"],
        warnings=state.get("warnings", []),
    )
    return {
        **state,
        "review_type": "sales_invoice_inventory_review",
        "response": response,
    }


async def validate_inventory_selection(state: SalesInvoiceWorkflowState) -> SalesInvoiceWorkflowState:
    payload = state["inventory_confirm_request"]
    preview = payload.source_preview
    recipient = payload.recipient or preview.recipient

    if not payload.selected_partner_id and recipient is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="selected_partner_id or recipient is required",
        )

    warnings = list(state.get("warnings", []))

    try:
        for line in payload.lines:
            await state["business_client"].get_inventory_item(
                state["user_id"],
                company_id=state["company_id"],
                item_id=line.inventory_item_id,
            )
            stock = await state["business_client"].get_stock_levels(
                state["user_id"],
                company_id=state["company_id"],
                item_id=line.inventory_item_id,
                location_id=line.inventory_location_id,
                limit=1,
            )
            if not stock.levels:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Selected inventory item has no stock level at the selected location",
                )
            available = stock.levels[0].available_quantity
            if available < line.quantity:
                warnings.append(
                    f"Line {line.line_index + 1}: Requested quantity {line.quantity} exceeds selected-location stock {available}."
                )
    except BusinessClientError as exc:
        raise map_business_client_error(exc) from exc

    return {**state, "warnings": warnings}


def build_invoice_draft(state: SalesInvoiceWorkflowState) -> SalesInvoiceWorkflowState:
    payload = state["inventory_confirm_request"]
    source = payload.source_preview
    today = date.today()
    recipient = payload.recipient or source.recipient

    invoice = InvoiceCreate(
        company_id=state["company_id"],
        partner_id=payload.selected_partner_id,
        recipient=recipient,
        counterparty=source.partner_query or (recipient.name if recipient else None),
        issue_date=source.issue_date or today,
        tax_event_date=source.tax_event_date or source.issue_date or today,
        due_date=source.due_date or _first_day_next_month(today),
        currency=source.currency,
        notes=source.notes,
        status="draft",
        items=[
            InvoiceItemCreate(
                description=line.description,
                quantity=line.quantity,
                unit_label=line.unit_label,
                unit_price=line.unit_price,
                vat_rate=line.vat_rate,
                category=line.category,
                inventory_item_id=line.inventory_item_id,
                inventory_location_id=line.inventory_location_id,
                stock_quantity=line.stock_quantity or line.quantity,
            )
            for line in payload.lines
        ],
    )

    partner_warnings = _partner_warnings(
        partner_candidates=state.get("partner_candidates", []),
        selected_partner_id=payload.selected_partner_id,
        recipient_selected=recipient is not None,
    )
    response = SalesInvoiceReviewResponse(
        company_id=state["company_id"],
        invoice_draft=invoice,
        inventory_warnings=state.get("warnings", []),
        partner_warnings=partner_warnings,
    )
    return {
        **state,
        "invoice_draft": invoice,
        "review_type": "sales_invoice_review",
        "response": response,
    }


async def create_invoice(state: SalesInvoiceWorkflowState) -> SalesInvoiceWorkflowState:
    payload = state["invoice_confirm_request"]
    if not payload.confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invoice confirmation is required",
        )
    if payload.invoice_draft.company_id != state["company_id"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invoice company scope mismatch",
        )
    try:
        invoice = await state["business_client"].create_invoice(
            state["user_id"],
            payload.invoice_draft,
        )
    except BusinessClientError as exc:
        raise map_business_client_error(exc) from exc
    response = SalesInvoiceCreatedResponse(invoice=invoice, warnings=state.get("warnings", []))
    return {
        **state,
        "review_type": "sales_invoice_created",
        "response": response,
    }


def build_preview_graph():
    graph = StateGraph(SalesInvoiceWorkflowState)
    graph.add_node("validate_scope", validate_scope)
    graph.add_node("resolve_partner", resolve_partner)
    graph.add_node("resolve_inventory", resolve_inventory)
    graph.add_node("build_inventory_review", build_inventory_review)
    graph.set_entry_point("validate_scope")
    graph.add_edge("validate_scope", "resolve_partner")
    graph.add_edge("resolve_partner", "resolve_inventory")
    graph.add_edge("resolve_inventory", "build_inventory_review")
    graph.add_edge("build_inventory_review", END)
    return graph.compile()


def build_inventory_confirm_graph():
    graph = StateGraph(SalesInvoiceWorkflowState)
    graph.add_node("validate_scope", validate_scope)
    graph.add_node("validate_inventory_selection", validate_inventory_selection)
    graph.add_node("build_invoice_draft", build_invoice_draft)
    graph.set_entry_point("validate_scope")
    graph.add_edge("validate_scope", "validate_inventory_selection")
    graph.add_edge("validate_inventory_selection", "build_invoice_draft")
    graph.add_edge("build_invoice_draft", END)
    return graph.compile()


def build_invoice_confirm_graph():
    graph = StateGraph(SalesInvoiceWorkflowState)
    graph.add_node("validate_scope", validate_scope)
    graph.add_node("create_invoice", create_invoice)
    graph.set_entry_point("validate_scope")
    graph.add_edge("validate_scope", "create_invoice")
    graph.add_edge("create_invoice", END)
    return graph.compile()


_PREVIEW_GRAPH = build_preview_graph()
_INVENTORY_CONFIRM_GRAPH = build_inventory_confirm_graph()
_INVOICE_CONFIRM_GRAPH = build_invoice_confirm_graph()


async def run_preview_graph(
    *,
    user_id: str,
    agent_id: str,
    agent_repo: AgentRepository,
    business_client: BusinessClient,
    payload: CreateSalesInvoiceInventoryPreviewRequest,
) -> SalesInvoiceInventoryReviewResponse:
    initial_state: SalesInvoiceWorkflowState = {
        "user_id": user_id,
        "agent_id": agent_id,
        "agent_repo": agent_repo,
        "business_client": business_client,
        "preview_request": payload,
        "warnings": [],
    }
    state = await _PREVIEW_GRAPH.ainvoke(initial_state)
    return state["response"]


async def run_inventory_confirm_graph(
    *,
    user_id: str,
    agent_id: str,
    agent_repo: AgentRepository,
    business_client: BusinessClient,
    payload: ConfirmSalesInvoiceInventoryRequest,
) -> SalesInvoiceReviewResponse:
    initial_state: SalesInvoiceWorkflowState = {
        "user_id": user_id,
        "agent_id": agent_id,
        "agent_repo": agent_repo,
        "business_client": business_client,
        "inventory_confirm_request": payload,
        "partner_candidates": [],
        "warnings": [],
    }
    state = await _INVENTORY_CONFIRM_GRAPH.ainvoke(initial_state)
    return state["response"]


async def run_invoice_confirm_graph(
    *,
    user_id: str,
    agent_id: str,
    agent_repo: AgentRepository,
    business_client: BusinessClient,
    payload: ConfirmSalesInvoiceRequest,
) -> SalesInvoiceCreatedResponse:
    initial_state: SalesInvoiceWorkflowState = {
        "user_id": user_id,
        "agent_id": agent_id,
        "agent_repo": agent_repo,
        "business_client": business_client,
        "invoice_confirm_request": payload,
        "warnings": [],
    }
    state = await _INVOICE_CONFIRM_GRAPH.ainvoke(initial_state)
    return state["response"]

