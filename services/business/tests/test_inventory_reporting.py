from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.inventory.models import InventoryItemInDB, InventoryLocationInDB, ReorderReportRow
from app.inventory.services.inventory_reporting_service import InventoryReportingService


def _item(item_id: str = "item-1") -> InventoryItemInDB:
    now = datetime.now(timezone.utc)
    return InventoryItemInDB(
        id=item_id,
        user_id="u1",
        created_by_user_id="u1",
        updated_by_user_id="u1",
        company_id="c1",
        sku="SKU-1",
        name="Widget",
        unit="pcs",
        reorder_point=Decimal("5"),
        created_at=now,
        updated_at=now,
    )


class InventoryReportingServiceTests(unittest.IsolatedAsyncioTestCase):
    def _make_service(self) -> InventoryReportingService:
        return InventoryReportingService(
            item_repo=AsyncMock(),
            location_repo=AsyncMock(),
            movement_repo=AsyncMock(),
            company_service=AsyncMock(),
        )

    async def test_get_overview_combines_repo_counts(self) -> None:
        service = self._make_service()
        service.item_repo.count_statuses.return_value = type("Counts", (), {"total": 10, "active": 8, "inactive": 2})()
        service.item_repo.count_categories.return_value = 4
        service.location_repo.count_by_company.return_value = 3
        service.movement_repo.count_low_and_negative_stock.return_value = (2, 1)

        result = await service.get_overview("u1", "c1")

        self.assertEqual(result.total_item_count, 10)
        self.assertEqual(result.low_stock_count, 2)
        self.assertEqual(result.negative_stock_count, 1)
        service.company_service.require_company.assert_awaited_once_with("u1", "c1")

    async def test_get_reorder_report_returns_paginated_response(self) -> None:
        service = self._make_service()
        service.movement_repo.reorder_report.return_value = (
            [
                ReorderReportRow(
                    item_id="item-1",
                    item_name="Widget",
                    sku="SKU-1",
                    location_id="loc-1",
                    location_name="Main",
                    available_quantity=Decimal("2"),
                    reorder_point=Decimal("5"),
                    suggested_reorder_quantity=Decimal("8"),
                )
            ],
            1,
        )

        result = await service.get_reorder_report("u1", "c1", limit=20, offset=0)

        self.assertEqual(result.total_count, 1)
        self.assertEqual(result.rows[0].item_name, "Widget")

    async def test_list_negative_stock_hydrates_item_and_location_names(self) -> None:
        service = self._make_service()
        now = datetime.now(timezone.utc)
        service.movement_repo.negative_stock_levels.return_value = (
            [{"item_id": "item-1", "location_id": "loc-1", "available_quantity": Decimal("-2")}],
            1,
        )
        service.item_repo.get_many_by_ids.return_value = {"item-1": _item("item-1")}
        service.location_repo.get_many_by_ids.return_value = {
            "loc-1": InventoryLocationInDB(
                id="loc-1",
                user_id="u1",
                company_id="c1",
                name="Main",
                created_at=now,
                updated_at=now,
            )
        }

        result = await service.list_negative_stock("u1", "c1", limit=20, offset=0)

        self.assertEqual(result.total_count, 1)
        self.assertEqual(result.levels[0].item_name, "Widget")
        self.assertEqual(result.levels[0].available_quantity, Decimal("-2"))


if __name__ == "__main__":
    unittest.main()
