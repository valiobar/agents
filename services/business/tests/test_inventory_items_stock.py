from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.inventory.models import (
    InventoryCategoryListResponse,
    InventoryCategorySummary,
    InventoryItemFilters,
    InventoryItemInDB,
    InventoryLocationInDB,
    StockLevelFilters,
)
from app.inventory.services.inventory_service import InventoryService


def _item(item_id: str = "it-1") -> InventoryItemInDB:
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
        created_at=now,
        updated_at=now,
    )


class InventoryItemStockAttachmentTests(unittest.IsolatedAsyncioTestCase):
    def _make_service(
        self,
        *,
        list_items: list[InventoryItemInDB],
        stock_map: dict[str, Decimal],
        get_by_id: InventoryItemInDB | None = None,
    ) -> InventoryService:
        item_repo = AsyncMock()
        item_repo.list_by_company = AsyncMock(return_value=list_items)
        item_repo.count_by_filters = AsyncMock(return_value=len(list_items))
        item_repo.get_by_id = AsyncMock(return_value=get_by_id)
        movement_repo = AsyncMock()
        movement_repo.aggregate_available_quantities = AsyncMock(return_value=stock_map)
        company_service = AsyncMock()
        company_service.require_company = AsyncMock(return_value=None)
        return InventoryService(
            item_repo=item_repo,
            location_repo=AsyncMock(),
            movement_repo=movement_repo,
            company_service=company_service,
        )

    async def test_list_items_attaches_aggregated_stock(self) -> None:
        rows = [_item("it-1"), _item("it-2")]
        svc = self._make_service(
            list_items=rows,
            stock_map={"it-1": Decimal("10"), "it-2": Decimal("3")},
        )
        filters = InventoryItemFilters(company_id="c1")
        result = await svc.list_items("u1", filters, 50, 0)
        self.assertEqual(result.total_count, 2)
        self.assertEqual(result.returned_count, 2)
        by_id = {r.id: r.available_in_stock for r in result.items}
        self.assertEqual(by_id["it-1"], Decimal("10"))
        self.assertEqual(by_id["it-2"], Decimal("3"))
        svc.movement_repo.aggregate_available_quantities.assert_awaited_once_with(
            user_id="u1",
            company_id="c1",
            item_ids=["it-1", "it-2"],
        )

    async def test_list_items_uses_zero_when_no_movement_aggregate(self) -> None:
        rows = [_item("it-1")]
        svc = self._make_service(list_items=rows, stock_map={})
        filters = InventoryItemFilters(company_id="c1")
        result = await svc.list_items("u1", filters, 50, 0)
        self.assertEqual(result.items[0].available_in_stock, Decimal("0"))

    async def test_get_item_attaches_stock(self) -> None:
        one = _item("it-1")
        svc = self._make_service(
            list_items=[],
            stock_map={"it-1": Decimal("42")},
            get_by_id=one,
        )
        got = await svc.get_item("u1", "c1", "it-1")
        self.assertEqual(got.id, "it-1")
        self.assertEqual(got.available_in_stock, Decimal("42"))
        svc.movement_repo.aggregate_available_quantities.assert_awaited_once_with(
            user_id="u1",
            company_id="c1",
            item_ids=["it-1"],
        )

    async def test_list_items_forwards_search_filter_to_repo(self) -> None:
        rows = [_item("it-1")]
        svc = self._make_service(list_items=rows, stock_map={"it-1": Decimal("2")})
        filters = InventoryItemFilters(company_id="c1", search="wid")

        await svc.list_items("u1", filters, 20, 0)

        svc.item_repo.count_by_filters.assert_awaited_once_with("u1", filters)
        svc.item_repo.list_by_company.assert_awaited_once_with("u1", filters, 20, 0)

    async def test_list_categories_delegates_to_repo(self) -> None:
        expected = InventoryCategoryListResponse(
            total_category_count=2,
            uncategorized_item_count=1,
            categories=[
                InventoryCategorySummary(category="beverages", item_count=3, active_item_count=2),
                InventoryCategorySummary(category="snacks", item_count=1, active_item_count=1),
            ],
        )
        svc = self._make_service(list_items=[], stock_map={})
        svc.item_repo.list_categories = AsyncMock(return_value=expected)

        result = await svc.list_categories("u1", "c1")

        svc.company_service.require_company.assert_awaited_once_with("u1", "c1")
        svc.item_repo.list_categories.assert_awaited_once_with("u1", "c1")
        self.assertEqual(result, expected)

    async def test_get_stock_levels_returns_paginated_envelope(self) -> None:
        now = datetime.now(timezone.utc)
        item = _item("it-1")
        location = InventoryLocationInDB(
            id="loc-1",
            user_id="u1",
            company_id="c1",
            name="Main",
            created_at=now,
            updated_at=now,
        )
        svc = self._make_service(list_items=[], stock_map={})
        svc.movement_repo.aggregate_levels_by_location = AsyncMock(
            return_value=(
                [{"item_id": "it-1", "location_id": "loc-1", "available_quantity": Decimal("7")}],
                1,
                1,
            )
        )
        svc.item_repo.get_many_by_ids = AsyncMock(return_value={"it-1": item})
        svc.location_repo.get_many_by_ids = AsyncMock(return_value={"loc-1": location})

        result = await svc.get_stock_levels(
            "u1",
            StockLevelFilters(company_id="c1", limit=25, offset=0, sort_direction="desc"),
        )

        self.assertEqual(result.total_stock_level_count, 1)
        self.assertEqual(result.unique_item_count, 1)
        self.assertEqual(result.returned_count, 1)
        self.assertEqual(result.levels[0].item_name, "Widget")
        svc.item_repo.get_many_by_ids.assert_awaited_once_with("u1", "c1", ["it-1"])
        svc.location_repo.get_many_by_ids.assert_awaited_once_with("u1", "c1", ["loc-1"])


if __name__ == "__main__":
    unittest.main()
