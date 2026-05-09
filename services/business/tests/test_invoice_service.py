from __future__ import annotations

import sys
import unittest
from asyncio import sleep
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.company.models import CompanyInDB
from app.financial.models import InvoiceCreate, InvoiceInDB, InvoicePartyInput
from app.financial.services.invoice_service import InvoiceService
from app.partner.models import PartnerInDB


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FakeInvoiceRepository:
    async def next_invoice_number(self, user_id: str, company_id: str, year: int) -> str:
        await sleep(0)
        _ = user_id
        _ = company_id
        _ = year
        return "INV-2026-00001"

    async def create(self, doc: dict[str, Any]) -> InvoiceInDB:
        await sleep(0)
        now = _now()
        return InvoiceInDB.model_validate(
            {
                "id": "invoice-1",
                "created_at": now,
                "updated_at": now,
                **doc,
            }
        )


class FakeCompanyService:
    async def require_company(self, user_id: str, company_id: str) -> CompanyInDB:
        await sleep(0)
        now = _now()
        return CompanyInDB(
            id=company_id,
            user_id=user_id,
            name="Acme Ltd",
            registration_number="123456789",
            vat_number=None,
            city="Sofia",
            country="Bulgaria",
            address="1 Business St",
            accountable_person="Ivan Ivanov",
            email=None,
            phone=None,
            logo_data_url=None,
            is_default=True,
            created_at=now,
            updated_at=now,
        )


class FakePartnerRepository:
    async def resolve_by_company_identifier(
        self,
        user_id: str,
        company_id: str,
        partner_id: str,
    ) -> PartnerInDB | None:
        await sleep(0)
        now = _now()
        return PartnerInDB(
            id=partner_id,
            user_id=user_id,
            company_id=company_id,
            kind="client",
            name="Client Ltd",
            registration_number="987654321",
            vat_number=None,
            city="Plovdiv",
            country="Bulgaria",
            address="2 Client St",
            accountable_person="Petar Petrov",
            email=None,
            phone=None,
            notes=None,
            created_at=now,
            updated_at=now,
        )


class FakeInventoryService:
    def __init__(self) -> None:
        self.issue_calls: list[dict[str, Any]] = []

    async def require_item_for_company(
        self,
        user_id: str,
        company_id: str,
        item_id: str,
        location_id: str | None = None,
    ) -> None:
        await sleep(0)
        _ = user_id
        _ = company_id
        _ = item_id
        _ = location_id

    async def issue_for_invoice(
        self,
        user_id: str,
        invoice_id: str,
        company_id: str,
        lines: list[dict[str, Any]],
    ) -> None:
        await sleep(0)
        self.issue_calls.append(
            {
                "user_id": user_id,
                "invoice_id": invoice_id,
                "company_id": company_id,
                "lines": lines,
            }
        )


def _payload(status: str) -> InvoiceCreate:
    return InvoiceCreate(
        company_id="company-1",
        partner_id=None,
        recipient=InvoicePartyInput(
            name="Client Ltd",
            registration_number="987654321",
            vat_number=None,
            city="Plovdiv",
            country="Bulgaria",
            address="2 Client St",
            accountable_person="Petar Petrov",
            logo_data_url=None,
        ),
        issue_date=date(2026, 5, 1),
        tax_event_date=date(2026, 5, 1),
        due_date=date(2026, 5, 10),
        place_of_supply="Bulgaria",
        payment_method="bank_transfer",
        currency="EUR",
        status=status,  # type: ignore[arg-type]
        items=[
            {
                "description": "BlueGrid 27-inch IPS Monitor Standard",
                "quantity": Decimal("2"),
                "unit_label": "pcs",
                "unit_price": Decimal("100"),
                "vat_rate": Decimal("0.20"),
                "category": "peripherals",
                "inventory_item_id": "item-1",
                "inventory_location_id": "location-1",
                "stock_quantity": Decimal("2"),
            }
        ],
    )


class InvoiceServiceStockIssueTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_invoice_issues_stock_for_sent_status(self) -> None:
        inventory_service = FakeInventoryService()
        service = InvoiceService(
            repo=FakeInvoiceRepository(),
            company_service=FakeCompanyService(),
            partner_repo=FakePartnerRepository(),
            inventory_service=inventory_service,
        )

        created = await service.create_invoice("user-1", _payload("sent"))

        self.assertEqual(created.status, "sent")
        self.assertEqual(len(inventory_service.issue_calls), 1)
        self.assertEqual(inventory_service.issue_calls[0]["invoice_id"], created.id)

    async def test_create_invoice_does_not_issue_stock_for_draft_status(self) -> None:
        inventory_service = FakeInventoryService()
        service = InvoiceService(
            repo=FakeInvoiceRepository(),
            company_service=FakeCompanyService(),
            partner_repo=FakePartnerRepository(),
            inventory_service=inventory_service,
        )

        created = await service.create_invoice("user-1", _payload("draft"))

        self.assertEqual(created.status, "draft")
        self.assertEqual(inventory_service.issue_calls, [])


if __name__ == "__main__":
    unittest.main()
