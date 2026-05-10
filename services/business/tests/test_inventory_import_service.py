from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

from pymongo.errors import DuplicateKeyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.inventory.models import (  # noqa: E402
    InventoryImportPreviewInDB,
    InventoryImportPreviewLine,
    InventoryItemInDB,
    SupplierInvoiceLineCandidate,
)
from app.inventory.services.inventory_import_service import InventoryImportService  # noqa: E402


def _item(*, item_id: str, sku: str) -> InventoryItemInDB:
    now = datetime.now(timezone.utc)
    return InventoryItemInDB(
        id=item_id,
        user_id="u1",
        created_by_user_id="u1",
        updated_by_user_id="u1",
        company_id="c1",
        sku=sku,
        name="Generated item",
        unit="pcs",
        created_at=now,
        updated_at=now,
    )


def _line_without_proposed_item() -> InventoryImportPreviewLine:
    return InventoryImportPreviewLine(
        candidate=SupplierInvoiceLineCandidate(
            description="Consulting line",
            sku=None,
            barcode=None,
            quantity=Decimal("1"),
            unit="pcs",
            unit_price=Decimal("42.00"),
        ),
        matched_item_id=None,
        proposed_item=None,
        location_id="loc-1",
        receipt_quantity=Decimal("1"),
        warnings=[],
    )


def _preview_with_line(line: InventoryImportPreviewLine) -> InventoryImportPreviewInDB:
    now = datetime.now(timezone.utc)
    return InventoryImportPreviewInDB(
        id="preview-1",
        user_id="u1",
        company_id="c1",
        document_id="doc-1",
        source_type="supplier_invoice_upload",
        status="draft",
        lines=[line],
        created_at=now,
        updated_at=now,
    )


class InventoryImportServiceSkuGenerationTests(unittest.IsolatedAsyncioTestCase):
    def _make_service(self, *, item_repo: AsyncMock) -> InventoryImportService:
        return InventoryImportService(
            preview_repo=AsyncMock(),
            item_repo=item_repo,
            location_repo=AsyncMock(),
            movement_repo=AsyncMock(),
            company_service=AsyncMock(),
        )

    async def test_resolve_line_item_creates_item_when_proposed_missing(self) -> None:
        line = _line_without_proposed_item()
        preview = _preview_with_line(line)

        item_repo = AsyncMock()
        item_repo.find_by_sku = AsyncMock(side_effect=[None, None])
        item_repo.create = AsyncMock(return_value=_item(item_id="it-1", sku="AUTO-CONSULTING-LINE-1"))

        service = self._make_service(item_repo=item_repo)
        item_id, items_created, items_updated = await service._resolve_line_item_id(
            user_id="u1",
            preview=preview,
            line=line,
            line_index=0,
        )

        self.assertEqual(item_id, "it-1")
        self.assertEqual(items_created, 1)
        self.assertEqual(items_updated, 0)
        payload = item_repo.create.await_args.kwargs["payload"]
        self.assertTrue(payload.sku.startswith("AUTO-CONSULTING-LINE-1"))
        self.assertEqual(payload.name, "Consulting line")
        self.assertEqual(payload.unit, "pcs")

    async def test_resolve_line_item_retries_with_next_generated_sku_on_duplicate(self) -> None:
        line = _line_without_proposed_item()
        preview = _preview_with_line(line)

        item_repo = AsyncMock()
        item_repo.find_by_sku = AsyncMock(
            side_effect=[
                _item(item_id="existing-base", sku="AUTO-CONSULTING-LINE-1"),
                None,
                None,
                _item(item_id="race", sku="AUTO-CONSULTING-LINE-1-2"),
                None,
            ]
        )
        item_repo.create = AsyncMock(
            side_effect=[
                DuplicateKeyError("duplicate key"),
                _item(item_id="it-2", sku="AUTO-CONSULTING-LINE-1-3"),
            ]
        )

        service = self._make_service(item_repo=item_repo)
        item_id, items_created, items_updated = await service._resolve_line_item_id(
            user_id="u1",
            preview=preview,
            line=line,
            line_index=0,
        )

        self.assertEqual(item_id, "it-2")
        self.assertEqual(items_created, 1)
        self.assertEqual(items_updated, 0)
        first_payload = item_repo.create.await_args_list[0].kwargs["payload"]
        second_payload = item_repo.create.await_args_list[1].kwargs["payload"]
        self.assertEqual(first_payload.sku, "AUTO-CONSULTING-LINE-1-2")
        self.assertEqual(second_payload.sku, "AUTO-CONSULTING-LINE-1-3")

    async def test_confirm_preview_line_skips_item_creation_when_source_movement_exists(self) -> None:
        line = _line_without_proposed_item()
        preview = _preview_with_line(line)

        item_repo = AsyncMock()
        item_repo.find_by_sku = AsyncMock()
        item_repo.create = AsyncMock()

        movement_repo = AsyncMock()
        movement_repo.has_source_movement = AsyncMock(return_value=True)
        movement_repo.insert = AsyncMock()

        location_repo = AsyncMock()
        location_repo.exists = AsyncMock(return_value=True)

        service = InventoryImportService(
            preview_repo=AsyncMock(),
            item_repo=item_repo,
            location_repo=location_repo,
            movement_repo=movement_repo,
            company_service=AsyncMock(),
        )

        items_created, items_updated, movements_created = await service._confirm_preview_line(
            user_id="u1",
            preview=preview,
            line=line,
            line_index=0,
        )

        self.assertEqual(items_created, 0)
        self.assertEqual(items_updated, 0)
        self.assertEqual(movements_created, 0)
        item_repo.create.assert_not_awaited()
        movement_repo.insert.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
