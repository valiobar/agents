from __future__ import annotations

import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import unittest

from fastapi import HTTPException, status

from app.models.financial import (
    InvoiceCreate,
    InvoiceItem,
    InvoiceResponse,
    PartnerMatchCandidate,
    PartnerResolveResponse,
    PartnerResponse,
)
from app.models.inventory import (
    InventoryItemResponse,
    InventorySearchMatch,
    InventorySearchRequest,
    InventorySearchResponse,
    ResolveInventoryItemRequest,
    ResolveInventoryItemResponse,
    StockLevel,
    StockLevelListResponse,
)
from app.models.sales_invoice_workflow import (
    ConfirmedSalesInvoiceInventoryLine,
    ConfirmSalesInvoiceInventoryRequest,
    ConfirmSalesInvoiceRequest,
    CreateSalesInvoiceInventoryPreviewRequest,
    RequestedSalesInvoiceLine,
)
from app.models.shared.agent import AgentConfig, AgentInDB
from app.services.sales_invoice_workflow_graph import (
    run_inventory_confirm_graph,
    run_invoice_confirm_graph,
    run_preview_graph,
)


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


def _partner(partner_id: str = "partner-1") -> PartnerResponse:
    now = _utc_now()
    return PartnerResponse(
        id=partner_id,
        user_id="user-1",
        company_id="company-1",
        kind="client",
        name="Acme Corp",
        registration_number="REG-1",
        vat_number=None,
        city="Sofia",
        country="Bulgaria",
        address="Main 1",
        accountable_person="Ivan",
        email=None,
        phone=None,
        notes=None,
        created_at=now,
        updated_at=now,
    )


def _stock_levels(*, item_id: str, qty: Decimal, location_id: str = "loc-1") -> StockLevelListResponse:
    level = StockLevel(
        item_id=item_id,
        item_name="Widget",
        item_sku="W-1",
        location_id=location_id,
        location_name="Main",
        available_quantity=qty,
        unit="pcs",
    )
    return StockLevelListResponse(
        total_stock_level_count=1,
        unique_item_count=1,
        returned_count=1,
        offset=0,
        limit=20,
        truncated=False,
        next_offset=None,
        levels=[level],
    )


def _empty_stock_levels() -> StockLevelListResponse:
    return StockLevelListResponse(
        total_stock_level_count=0,
        unique_item_count=0,
        returned_count=0,
        offset=0,
        limit=20,
        truncated=False,
        next_offset=None,
        levels=[],
    )


def _exact_match(
    *,
    item_id: str = "item-1",
    name: str = "Widget",
    confidence: float = 0.98,
    available: Decimal | None = Decimal("100"),
) -> InventorySearchMatch:
    return InventorySearchMatch(
        item_id=item_id,
        name=name,
        sku="W-1",
        unit="pcs",
        selling_price=Decimal("10.00"),
        confidence=confidence,
        match_reason="sku",
        available_quantity=available,
    )


def _invoice_response(user_id: str, payload: InvoiceCreate) -> InvoiceResponse:
    now = _utc_now()
    items_out: list[InvoiceItem] = []
    subtotal = Decimal("0")
    vat_total = Decimal("0")
    for it in payload.items:
        line_sub = it.quantity * it.unit_price
        line_vat = line_sub * it.vat_rate
        subtotal += line_sub
        vat_total += line_vat
        items_out.append(
            InvoiceItem(
                description=it.description,
                quantity=it.quantity,
                unit_label=it.unit_label,
                unit_price=it.unit_price,
                vat_rate=it.vat_rate,
                category=it.category,
                inventory_item_id=it.inventory_item_id,
                inventory_location_id=it.inventory_location_id,
                stock_quantity=it.stock_quantity,
                subtotal=line_sub,
                vat_amount=line_vat,
                total=line_sub + line_vat,
            )
        )
    return InvoiceResponse(
        id="inv-1",
        user_id=user_id,
        company_id=payload.company_id,
        partner_id=payload.partner_id,
        invoice_number="INV-1",
        counterparty=payload.counterparty,
        issue_date=payload.issue_date,
        tax_event_date=payload.tax_event_date,
        due_date=payload.due_date,
        currency=payload.currency,
        items=items_out,
        subtotal=subtotal,
        vat_total=vat_total,
        total=subtotal + vat_total,
        status=payload.status,
        notes=payload.notes,
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
    def __init__(self) -> None:
        self.partner_resolve = PartnerResolveResponse(candidates=[])
        self.inventory_by_query: dict[str, ResolveInventoryItemResponse] = {}
        self.search_by_query: dict[str, InventorySearchResponse] = {}
        self.stock_for_item: dict[str, StockLevelListResponse] = {}
        self.created_invoice: InvoiceCreate | None = None

    async def company_exists(self, user_id: str, company_id: str) -> bool:
        return True

    async def resolve_partner(self, user_id: str, payload: object) -> PartnerResolveResponse:
        return self.partner_resolve

    async def resolve_inventory_item(
        self, user_id: str, payload: ResolveInventoryItemRequest
    ) -> ResolveInventoryItemResponse:
        return self.inventory_by_query[payload.query]

    async def search_inventory(self, user_id: str, payload: InventorySearchRequest) -> InventorySearchResponse:
        existing = self.search_by_query.get(payload.query)
        if existing is not None:
            return existing

        resolved = self.inventory_by_query[payload.query]
        matches = [*([] if resolved.exact_match is None else [resolved.exact_match]), *resolved.candidates]
        return InventorySearchResponse(
            query=payload.query,
            normalized_query=payload.query.lower(),
            matches=matches[: payload.limit],
            total_available_quantity=None,
        )

    async def get_stock_levels(
        self,
        user_id: str,
        *,
        company_id: str,
        item_id: str | None = None,
        location_id: str | None = None,
        limit: int = 50,
        **_: object,
    ) -> StockLevelListResponse:
        assert item_id is not None
        return self.stock_for_item.get(item_id, _empty_stock_levels())

    async def get_inventory_item(
        self,
        user_id: str,
        *,
        company_id: str,
        item_id: str,
    ) -> InventoryItemResponse:
        now = _utc_now()
        return InventoryItemResponse(
            id=item_id,
            user_id=user_id,
            company_id=company_id,
            sku="W-1",
            name="Widget",
            unit="pcs",
            created_at=now,
            updated_at=now,
        )

    async def create_invoice(self, user_id: str, payload: InvoiceCreate) -> InvoiceResponse:
        self.created_invoice = payload
        return _invoice_response(user_id, payload)


def _preview_payload() -> CreateSalesInvoiceInventoryPreviewRequest:
    return CreateSalesInvoiceInventoryPreviewRequest(
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
    )


class SalesInvoiceWorkflowGraphTests(unittest.IsolatedAsyncioTestCase):
    async def test_preview_exact_match_selects_item_and_default_location(self) -> None:
        business = FakeBusinessClient()
        business.inventory_by_query["W-1"] = ResolveInventoryItemResponse(
            query="W-1",
            normalized_query="w-1",
            exact_match=_exact_match(),
            candidates=[],
        )
        business.stock_for_item["item-1"] = _stock_levels(item_id="item-1", qty=Decimal("50"))

        response = await run_preview_graph(
            user_id="user-1",
            agent_id="agent-1",
            agent_repo=FakeAgentRepo(_agent(user_id="user-1", agent_id="agent-1", company_id="company-1")),
            business_client=business,
            payload=_preview_payload(),
        )

        self.assertEqual(response.type, "sales_invoice_inventory_review")
        line = response.lines[0]
        self.assertEqual(line.selected_item_id, "item-1")
        self.assertEqual(line.selected_location_id, "loc-1")

    async def test_preview_ambiguous_low_confidence_does_not_auto_select(self) -> None:
        business = FakeBusinessClient()
        low = _exact_match(confidence=0.85)
        business.inventory_by_query["W-1"] = ResolveInventoryItemResponse(
            query="W-1",
            normalized_query="w-1",
            exact_match=low,
            candidates=[low],
        )
        business.stock_for_item["item-1"] = _stock_levels(item_id="item-1", qty=Decimal("50"))

        response = await run_preview_graph(
            user_id="user-1",
            agent_id="agent-1",
            agent_repo=FakeAgentRepo(_agent(user_id="user-1", agent_id="agent-1", company_id="company-1")),
            business_client=business,
            payload=_preview_payload(),
        )

        self.assertIsNone(response.lines[0].selected_item_id)
        self.assertGreaterEqual(len(response.lines[0].candidates), 1)
        self.assertEqual(response.lines[0].stock_levels[0].item_id, "item-1")
        self.assertEqual(response.lines[0].stock_levels[0].location_id, "loc-1")

    async def test_preview_inventory_candidates_are_top_five_by_confidence(self) -> None:
        business = FakeBusinessClient()
        candidates = [
            _exact_match(item_id="item-1", name="Item 1", confidence=0.71),
            _exact_match(item_id="item-2", name="Item 2", confidence=0.95),
            _exact_match(item_id="item-3", name="Item 3", confidence=0.82),
            _exact_match(item_id="item-4", name="Item 4", confidence=0.90),
            _exact_match(item_id="item-5", name="Item 5", confidence=0.65),
            _exact_match(item_id="item-6", name="Item 6", confidence=0.88),
            _exact_match(item_id="item-2", name="Item 2 duplicate", confidence=0.80),
        ]
        business.inventory_by_query["W-1"] = ResolveInventoryItemResponse(
            query="W-1",
            normalized_query="w-1",
            exact_match=None,
            candidates=candidates,
        )
        for candidate in candidates:
            business.stock_for_item[candidate.item_id] = _stock_levels(
                item_id=candidate.item_id,
                qty=Decimal("50"),
                location_id=f"loc-{candidate.item_id}",
            )

        response = await run_preview_graph(
            user_id="user-1",
            agent_id="agent-1",
            agent_repo=FakeAgentRepo(_agent(user_id="user-1", agent_id="agent-1", company_id="company-1")),
            business_client=business,
            payload=_preview_payload(),
        )

        line = response.lines[0]
        self.assertEqual(
            [candidate.item_id for candidate in line.candidates],
            ["item-2", "item-4", "item-6", "item-3", "item-1"],
        )
        self.assertEqual(
            {level.item_id for level in line.stock_levels},
            {"item-1", "item-2", "item-3", "item-4", "item-6"},
        )

    async def test_preview_missing_match_no_selection(self) -> None:
        business = FakeBusinessClient()
        business.inventory_by_query["W-1"] = ResolveInventoryItemResponse(
            query="W-1",
            normalized_query="w-1",
            exact_match=None,
            candidates=[],
        )

        response = await run_preview_graph(
            user_id="user-1",
            agent_id="agent-1",
            agent_repo=FakeAgentRepo(_agent(user_id="user-1", agent_id="agent-1", company_id="company-1")),
            business_client=business,
            payload=_preview_payload(),
        )

        self.assertIsNone(response.lines[0].selected_item_id)
        self.assertTrue(any("No high-confidence" in w for w in response.warnings))

    async def test_preview_stock_warning_when_requested_exceeds_available(self) -> None:
        business = FakeBusinessClient()
        business.inventory_by_query["W-1"] = ResolveInventoryItemResponse(
            query="W-1",
            normalized_query="w-1",
            exact_match=_exact_match(),
            candidates=[],
        )
        business.stock_for_item["item-1"] = _stock_levels(item_id="item-1", qty=Decimal("1"))

        response = await run_preview_graph(
            user_id="user-1",
            agent_id="agent-1",
            agent_repo=FakeAgentRepo(_agent(user_id="user-1", agent_id="agent-1", company_id="company-1")),
            business_client=business,
            payload=_preview_payload(),
        )

        self.assertTrue(any("exceeds available stock" in w for w in response.warnings))

    async def test_preview_partner_candidates_surface_ambiguity(self) -> None:
        p1, p2 = _partner("p-1"), _partner("p-2")
        business = FakeBusinessClient()
        business.partner_resolve = PartnerResolveResponse(
            candidates=[
                PartnerMatchCandidate(partner=p1, match_type="name_prefix", score=0.9, match_reasons=[]),
                PartnerMatchCandidate(partner=p2, match_type="contains", score=0.7, match_reasons=[]),
            ]
        )
        business.inventory_by_query["W-1"] = ResolveInventoryItemResponse(
            query="W-1",
            normalized_query="w-1",
            exact_match=_exact_match(),
            candidates=[],
        )
        business.stock_for_item["item-1"] = _stock_levels(item_id="item-1", qty=Decimal("50"))

        response = await run_preview_graph(
            user_id="user-1",
            agent_id="agent-1",
            agent_repo=FakeAgentRepo(_agent(user_id="user-1", agent_id="agent-1", company_id="company-1")),
            business_client=business,
            payload=_preview_payload(),
        )

        self.assertEqual(len(response.partner_candidates), 2)

    async def test_preview_rejects_missing_agent_via_guard(self) -> None:
        business = FakeBusinessClient()
        business.inventory_by_query["W-1"] = ResolveInventoryItemResponse(
            query="W-1",
            normalized_query="w-1",
            exact_match=_exact_match(),
            candidates=[],
        )
        business.stock_for_item["item-1"] = _stock_levels(item_id="item-1", qty=Decimal("50"))

        with self.assertRaises(HTTPException) as ctx:
            await run_preview_graph(
                user_id="user-1",
                agent_id="agent-1",
                agent_repo=FakeAgentRepo(None),
                business_client=business,
                payload=_preview_payload(),
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_404_NOT_FOUND)

    async def test_inventory_confirm_builds_draft_with_inventory_linkage(self) -> None:
        business = FakeBusinessClient()
        preview = _preview_payload()
        business.stock_for_item["item-1"] = _stock_levels(item_id="item-1", qty=Decimal("50"))

        confirm = ConfirmSalesInvoiceInventoryRequest(
            source_preview=preview,
            selected_partner_id="partner-1",
            lines=[
                ConfirmedSalesInvoiceInventoryLine(
                    line_index=0,
                    description="Widget",
                    quantity=Decimal("2"),
                    unit_label="pcs",
                    unit_price=Decimal("10.00"),
                    vat_rate=Decimal("0.20"),
                    inventory_item_id="item-1",
                    inventory_location_id="loc-1",
                )
            ],
        )

        response = await run_inventory_confirm_graph(
            user_id="user-1",
            agent_id="agent-1",
            agent_repo=FakeAgentRepo(_agent(user_id="user-1", agent_id="agent-1", company_id="company-1")),
            business_client=business,
            payload=confirm,
        )

        self.assertEqual(response.type, "sales_invoice_review")
        item = response.invoice_draft.items[0]
        self.assertEqual(item.inventory_item_id, "item-1")
        self.assertEqual(item.inventory_location_id, "loc-1")

    async def test_invoice_confirm_rejects_unconfirmed(self) -> None:
        business = FakeBusinessClient()
        preview = _preview_payload()
        business.stock_for_item["item-1"] = _stock_levels(item_id="item-1", qty=Decimal("50"))
        draft = (
            await run_inventory_confirm_graph(
                user_id="user-1",
                agent_id="agent-1",
                agent_repo=FakeAgentRepo(_agent(user_id="user-1", agent_id="agent-1", company_id="company-1")),
                business_client=business,
                payload=ConfirmSalesInvoiceInventoryRequest(
                    source_preview=preview,
                    selected_partner_id="partner-1",
                    lines=[
                        ConfirmedSalesInvoiceInventoryLine(
                            line_index=0,
                            description="Widget",
                            quantity=Decimal("2"),
                            unit_label="pcs",
                            unit_price=Decimal("10.00"),
                            vat_rate=Decimal("0.20"),
                            inventory_item_id="item-1",
                            inventory_location_id="loc-1",
                        )
                    ],
                ),
            )
        ).invoice_draft

        with self.assertRaises(HTTPException) as ctx:
            await run_invoice_confirm_graph(
                user_id="user-1",
                agent_id="agent-1",
                agent_repo=FakeAgentRepo(_agent(user_id="user-1", agent_id="agent-1", company_id="company-1")),
                business_client=business,
                payload=ConfirmSalesInvoiceRequest(invoice_draft=draft, confirmed=False),
            )
        self.assertEqual(ctx.exception.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)

    async def test_invoice_confirm_calls_business_when_confirmed(self) -> None:
        business = FakeBusinessClient()
        preview = _preview_payload()
        business.inventory_by_query["W-1"] = ResolveInventoryItemResponse(
            query="W-1",
            normalized_query="w-1",
            exact_match=_exact_match(item_id="item-1"),
            candidates=[],
        )
        business.stock_for_item["item-1"] = _stock_levels(item_id="item-1", qty=Decimal("50"))

        draft = (
            await run_inventory_confirm_graph(
                user_id="user-1",
                agent_id="agent-1",
                agent_repo=FakeAgentRepo(_agent(user_id="user-1", agent_id="agent-1", company_id="company-1")),
                business_client=business,
                payload=ConfirmSalesInvoiceInventoryRequest(
                    source_preview=preview,
                    selected_partner_id="partner-1",
                    lines=[
                        ConfirmedSalesInvoiceInventoryLine(
                            line_index=0,
                            description="Widget",
                            quantity=Decimal("2"),
                            unit_label="pcs",
                            unit_price=Decimal("10.00"),
                            vat_rate=Decimal("0.20"),
                            inventory_item_id="item-1",
                            inventory_location_id="loc-1",
                        )
                    ],
                ),
            )
        ).invoice_draft

        result = await run_invoice_confirm_graph(
            user_id="user-1",
            agent_id="agent-1",
            agent_repo=FakeAgentRepo(_agent(user_id="user-1", agent_id="agent-1", company_id="company-1")),
            business_client=business,
            payload=ConfirmSalesInvoiceRequest(invoice_draft=draft, confirmed=True),
        )

        self.assertEqual(result.type, "sales_invoice_created")
        self.assertIsNotNone(business.created_invoice)
        self.assertEqual(business.created_invoice.partner_id, "partner-1")


if __name__ == "__main__":
    unittest.main()
