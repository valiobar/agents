from __future__ import annotations

import sys
import unittest
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.dependencies import get_sales_invoice_workflow_service
from app.main import app
from app.models.financial import InvoiceCreate, InvoiceItemCreate
from app.models.sales_invoice_workflow import (
    ConfirmSalesInvoiceInventoryRequest,
    ConfirmSalesInvoiceRequest,
    ConfirmedSalesInvoiceInventoryLine,
    CreateSalesInvoiceInventoryPreviewRequest,
    RequestedSalesInvoiceLine,
    SalesInvoiceCreatedResponse,
    SalesInvoiceInventoryReviewResponse,
    SalesInvoiceReviewResponse,
)
from app.models.shared.agent import AgentConfig, AgentInDB
from app.services.sales_invoice_workflow_service import SalesInvoiceWorkflowService


@asynccontextmanager
async def _noop_lifespan(_app):
    yield


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
    async def company_exists(self, user_id: str, company_id: str) -> bool:
        return True


class FakeSalesInvoiceWorkflowService:
    def __init__(self) -> None:
        self.last_preview: CreateSalesInvoiceInventoryPreviewRequest | None = None
        self.last_inventory_confirm: ConfirmSalesInvoiceInventoryRequest | None = None
        self.last_invoice_confirm: ConfirmSalesInvoiceRequest | None = None

    async def create_preview(
        self,
        *,
        user_id: str,
        agent_id: str,
        payload: CreateSalesInvoiceInventoryPreviewRequest,
    ) -> SalesInvoiceInventoryReviewResponse:
        self.last_preview = payload
        return SalesInvoiceInventoryReviewResponse(
            company_id="company-1",
            partner_query=payload.partner_query,
            lines=[],
        )

    async def confirm_inventory(
        self,
        *,
        user_id: str,
        agent_id: str,
        payload: ConfirmSalesInvoiceInventoryRequest,
    ) -> SalesInvoiceReviewResponse:
        self.last_inventory_confirm = payload
        return SalesInvoiceReviewResponse(
            company_id="company-1",
            invoice_draft=InvoiceCreate(
                company_id="company-1",
                partner_id="partner-1",
                counterparty="Acme",
                issue_date=date.today(),
                tax_event_date=date.today(),
                due_date=date.today(),
                currency="EUR",
                items=[
                    InvoiceItemCreate(
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

    async def confirm_invoice(
        self,
        *,
        user_id: str,
        agent_id: str,
        payload: ConfirmSalesInvoiceRequest,
    ) -> SalesInvoiceCreatedResponse:
        self.last_invoice_confirm = payload
        if not payload.confirmed:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invoice confirmation is required",
            )
        raise AssertionError("confirm_invoice should not succeed in route tests without a full fake")


def _preview_json() -> dict[str, object]:
    return {
        "partner_query": "Acme",
        "currency": "EUR",
        "lines": [
            {
                "query": "W-1",
                "description": "Widget",
                "quantity": "2",
                "unit_price": "10.00",
                "vat_rate": "0.20",
            }
        ],
    }


class SalesInvoiceWorkflowRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        app.router.lifespan_context = _noop_lifespan
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_preview_route_uses_service_dependency_override(self) -> None:
        fake_service = FakeSalesInvoiceWorkflowService()
        app.dependency_overrides[get_sales_invoice_workflow_service] = lambda: fake_service

        response = self.client.post(
            "/agents/agent-1/invoice-workflows/sales-inventory/preview",
            headers={"x-user-id": "user-1"},
            json=_preview_json(),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["type"], "sales_invoice_inventory_review")
        self.assertIsNotNone(fake_service.last_preview)
        self.assertEqual(fake_service.last_preview.partner_query, "Acme")

    def test_preview_route_rejects_missing_agent(self) -> None:
        service = SalesInvoiceWorkflowService(FakeAgentRepo(None), FakeBusinessClient())
        app.dependency_overrides[get_sales_invoice_workflow_service] = lambda: service

        response = self.client.post(
            "/agents/agent-1/invoice-workflows/sales-inventory/preview",
            headers={"x-user-id": "user-1"},
            json=_preview_json(),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json()["detail"], "Agent not found")

    def test_preview_route_rejects_unassigned_agent(self) -> None:
        service = SalesInvoiceWorkflowService(
            FakeAgentRepo(_agent(user_id="user-1", agent_id="agent-1", company_id=None)),
            FakeBusinessClient(),
        )
        app.dependency_overrides[get_sales_invoice_workflow_service] = lambda: service

        response = self.client.post(
            "/agents/agent-1/invoice-workflows/sales-inventory/preview",
            headers={"x-user-id": "user-1"},
            json=_preview_json(),
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(
            response.json()["detail"],
            "Sales invoice inventory workflow requires a company-scoped agent",
        )

    def test_inventory_confirm_route_uses_service_dependency_override(self) -> None:
        fake_service = FakeSalesInvoiceWorkflowService()
        app.dependency_overrides[get_sales_invoice_workflow_service] = lambda: fake_service

        response = self.client.post(
            "/agents/agent-1/invoice-workflows/sales-inventory/inventory/confirm",
            headers={"x-user-id": "user-1"},
            json={
                "source_preview": _preview_json(),
                "selected_partner_id": "partner-1",
                "lines": [
                    {
                        "line_index": 0,
                        "description": "Widget",
                        "quantity": "2",
                        "unit_label": "pcs",
                        "unit_price": "10.00",
                        "vat_rate": "0.20",
                        "inventory_item_id": "item-1",
                        "inventory_location_id": "loc-1",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["type"], "sales_invoice_review")
        self.assertIsNotNone(fake_service.last_inventory_confirm)

    def test_invoice_confirm_route_rejects_unconfirmed(self) -> None:
        fake_service = FakeSalesInvoiceWorkflowService()
        app.dependency_overrides[get_sales_invoice_workflow_service] = lambda: fake_service

        response = self.client.post(
            "/agents/agent-1/invoice-workflows/sales-inventory/invoice/confirm",
            headers={"x-user-id": "user-1"},
            json={
                "confirmed": False,
                "invoice_draft": {
                    "company_id": "company-1",
                    "partner_id": "partner-1",
                    "counterparty": "Acme",
                    "issue_date": "2026-05-15",
                    "tax_event_date": "2026-05-15",
                    "due_date": "2026-06-01",
                    "currency": "EUR",
                    "items": [
                        {
                            "description": "Widget",
                            "quantity": "2",
                            "unit_label": "pcs",
                            "unit_price": "10.00",
                            "vat_rate": "0.20",
                            "inventory_item_id": "item-1",
                            "inventory_location_id": "loc-1",
                        }
                    ],
                },
            },
        )

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertEqual(response.json()["detail"], "Invoice confirmation is required")


if __name__ == "__main__":
    unittest.main()
