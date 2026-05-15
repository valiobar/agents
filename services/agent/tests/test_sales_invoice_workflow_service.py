from __future__ import annotations

import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest import IsolatedAsyncioTestCase

from fastapi import HTTPException, status

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clients.business import BusinessClientError
from app.models.inventory import (
    InventorySearchMatch,
    InventorySearchRequest,
    InventorySearchResponse,
    ResolveInventoryItemRequest,
    ResolveInventoryItemResponse,
    StockLevel,
    StockLevelListResponse,
)
from app.models.sales_invoice_workflow import (
    CreateSalesInvoiceInventoryPreviewRequest,
    RequestedSalesInvoiceLine,
    SalesInvoiceInventoryReviewResponse,
)
from app.models.shared.agent import AgentConfig, AgentInDB
from app.services.sales_invoice_workflow_service import SalesInvoiceWorkflowService


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _agent(*, user_id: str, agent_id: str, company_id: str | None) -> AgentInDB:
    now = _utc_now()
    return AgentInDB(
        id=agent_id,
        user_id=user_id,
        name="Accountant",
        description=None,
        agent_type="accountant",
        company_id=company_id,
        config=AgentConfig(),
        created_at=now,
        updated_at=now,
    )


class FakeAgentRepo:
    def __init__(self, agent: AgentInDB | None) -> None:
        self._agent = agent

    async def get_by_id(self, user_id: str, agent_id: str) -> AgentInDB | None:
        if self._agent is None:
            return None
        if self._agent.user_id != user_id or self._agent.id != agent_id:
            return None
        return self._agent


class FakeBusinessClient:
    def __init__(self, *, resolve_error: BusinessClientError | None = None) -> None:
        self.resolve_error = resolve_error
        self.resolve_calls: list[ResolveInventoryItemRequest] = []

    async def company_exists(self, user_id: str, company_id: str) -> bool:
        return True

    async def resolve_partner(self, user_id: str, payload: object) -> object:
        return type("PartnerResolve", (), {"candidates": []})()

    async def resolve_inventory_item(
        self, user_id: str, payload: ResolveInventoryItemRequest
    ) -> ResolveInventoryItemResponse:
        if self.resolve_error:
            raise self.resolve_error
        self.resolve_calls.append(payload)
        return ResolveInventoryItemResponse(
            query=payload.query,
            normalized_query=payload.query.lower(),
            exact_match=InventorySearchMatch(
                item_id="item-1",
                name="Widget",
                sku="W-1",
                unit="pcs",
                selling_price=Decimal("10.00"),
                confidence=0.98,
                match_reason="sku",
                available_quantity=Decimal("5"),
            ),
            candidates=[],
        )

    async def search_inventory(self, user_id: str, payload: InventorySearchRequest) -> InventorySearchResponse:
        match = InventorySearchMatch(
            item_id="item-1",
            name="Widget",
            sku="W-1",
            unit="pcs",
            selling_price=Decimal("10.00"),
            confidence=0.98,
            match_reason="sku",
            available_quantity=Decimal("5"),
        )
        return InventorySearchResponse(
            query=payload.query,
            normalized_query=payload.query.lower(),
            matches=[match],
            total_available_quantity=Decimal("5"),
        )

    async def get_stock_levels(self, user_id: str, **kwargs: object) -> StockLevelListResponse:
        return StockLevelListResponse(
            total_stock_level_count=1,
            unique_item_count=1,
            returned_count=1,
            offset=0,
            limit=20,
            truncated=False,
            next_offset=None,
            levels=[
                StockLevel(
                    item_id="item-1",
                    item_name="Widget",
                    item_sku="W-1",
                    location_id="loc-1",
                    location_name="Main",
                    available_quantity=Decimal("50"),
                    unit="pcs",
                )
            ],
        )


class SalesInvoiceWorkflowServiceTests(IsolatedAsyncioTestCase):
    async def test_preview_returns_inventory_review_for_exact_match(self) -> None:
        service = SalesInvoiceWorkflowService(
            FakeAgentRepo(_agent(user_id="user-1", agent_id="agent-1", company_id="company-1")),
            FakeBusinessClient(),
        )

        response = await service.create_preview(
            user_id="user-1",
            agent_id="agent-1",
            payload=CreateSalesInvoiceInventoryPreviewRequest(
                partner_query="Acme",
                lines=[
                    RequestedSalesInvoiceLine(
                        query="W-1",
                        description="Widget",
                        quantity=Decimal("2"),
                        unit_price=Decimal("10.00"),
                        vat_rate=Decimal("0.20"),
                    )
                ],
            ),
        )

        self.assertIsInstance(response, SalesInvoiceInventoryReviewResponse)
        self.assertEqual(response.type, "sales_invoice_inventory_review")
        self.assertEqual(response.lines[0].selected_item_id, "item-1")

    async def test_preview_maps_business_client_4xx(self) -> None:
        service = SalesInvoiceWorkflowService(
            FakeAgentRepo(_agent(user_id="user-1", agent_id="agent-1", company_id="company-1")),
            FakeBusinessClient(resolve_error=BusinessClientError("Conflict", status_code=409)),
        )

        with self.assertRaises(HTTPException) as ctx:
            await service.create_preview(
                user_id="user-1",
                agent_id="agent-1",
                payload=CreateSalesInvoiceInventoryPreviewRequest(
                    partner_query="Acme",
                    lines=[
                        RequestedSalesInvoiceLine(
                            query="W-1",
                            description="Widget",
                            quantity=Decimal("2"),
                        )
                    ],
                ),
            )

        self.assertEqual(ctx.exception.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(ctx.exception.detail, "Conflict")

    async def test_preview_maps_business_client_5xx(self) -> None:
        service = SalesInvoiceWorkflowService(
            FakeAgentRepo(_agent(user_id="user-1", agent_id="agent-1", company_id="company-1")),
            FakeBusinessClient(resolve_error=BusinessClientError("Business failed", status_code=500)),
        )

        with self.assertRaises(HTTPException) as ctx:
            await service.create_preview(
                user_id="user-1",
                agent_id="agent-1",
                payload=CreateSalesInvoiceInventoryPreviewRequest(
                    partner_query="Acme",
                    lines=[
                        RequestedSalesInvoiceLine(
                            query="W-1",
                            description="Widget",
                            quantity=Decimal("2"),
                        )
                    ],
                ),
            )

        self.assertEqual(ctx.exception.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    async def test_preview_rejects_missing_agent(self) -> None:
        service = SalesInvoiceWorkflowService(FakeAgentRepo(None), FakeBusinessClient())

        with self.assertRaises(HTTPException) as ctx:
            await service.create_preview(
                user_id="user-1",
                agent_id="agent-1",
                payload=CreateSalesInvoiceInventoryPreviewRequest(
                    partner_query="Acme",
                    lines=[
                        RequestedSalesInvoiceLine(
                            query="W-1",
                            description="Widget",
                            quantity=Decimal("2"),
                        )
                    ],
                ),
            )

        self.assertEqual(ctx.exception.status_code, status.HTTP_404_NOT_FOUND)
