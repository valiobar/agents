from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.inventory.repositories.inventory_item_repo import InventoryItemRepository


class InventoryCategoryFacetRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_categories_maps_facet_rows(self) -> None:
        repo = InventoryItemRepository(MagicMock())
        cursor = MagicMock()
        cursor.to_list = AsyncMock(
            return_value=[
                {
                    "categorized": [
                        {"_id": "beverages", "item_count": 4, "active_item_count": 3},
                        {"_id": "snacks", "item_count": 2, "active_item_count": 1},
                    ],
                    "uncategorized": [{"count": 5}],
                }
            ]
        )
        repo.collection = MagicMock()
        repo.collection.aggregate.return_value = cursor

        result = await repo.list_categories("user-1", "company-1")

        self.assertEqual(result.total_category_count, 2)
        self.assertEqual(result.uncategorized_item_count, 5)
        self.assertEqual([row.category for row in result.categories], ["beverages", "snacks"])
        self.assertEqual(result.categories[0].item_count, 4)
        self.assertEqual(result.categories[0].active_item_count, 3)
        aggregate_pipeline = repo.collection.aggregate.call_args.args[0]
        self.assertEqual(aggregate_pipeline[0]["$match"]["user_id"], "user-1")
        self.assertEqual(aggregate_pipeline[0]["$match"]["company_id"], "company-1")
        self.assertIn("$facet", aggregate_pipeline[2])

    async def test_list_categories_returns_empty_payload_for_no_rows(self) -> None:
        repo = InventoryItemRepository(MagicMock())
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=[])
        repo.collection = MagicMock()
        repo.collection.aggregate.return_value = cursor

        result = await repo.list_categories("user-1", "company-1")

        self.assertEqual(result.total_category_count, 0)
        self.assertEqual(result.uncategorized_item_count, 0)
        self.assertEqual(result.categories, [])


if __name__ == "__main__":
    unittest.main()
