from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.inventory.models import StockMovementCreate
from app.inventory.repositories.stock_movement_repo import StockMovementRepository


class _InsertResult:
    def __init__(self, inserted_id: str) -> None:
        self.inserted_id = inserted_id


class _FakeCollection:
    def __init__(self) -> None:
        self.inserted_docs: list[dict] = []

    async def insert_one(self, doc: dict) -> _InsertResult:
        self.inserted_docs.append(doc)
        return _InsertResult(inserted_id=f"m-{len(self.inserted_docs)}")


class _FakeDB:
    def __init__(self, collection: _FakeCollection) -> None:
        self._collection = collection

    def __getitem__(self, name: str) -> _FakeCollection:
        if name != "stock_movements":
            raise KeyError(name)
        return self._collection


class StockMovementRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_insert_excludes_none_source_fields(self) -> None:
        collection = _FakeCollection()
        repo = StockMovementRepository(_FakeDB(collection))
        payload = StockMovementCreate(
            company_id="c1",
            item_id="item-1",
            location_id="loc-1",
            movement_type="receipt",
            quantity_delta=Decimal("3"),
            reason="Manual restock",
            source_type=None,
            source_id=None,
            source_line_id=None,
        )

        await repo.insert(user_id="u1", payload=payload, performed_by_user_id="u1")
        await repo.insert(user_id="u1", payload=payload, performed_by_user_id="u1")

        self.assertEqual(len(collection.inserted_docs), 2)
        for inserted in collection.inserted_docs:
            self.assertNotIn("source_type", inserted)
            self.assertNotIn("source_id", inserted)
            self.assertNotIn("source_line_id", inserted)


if __name__ == "__main__":
    unittest.main()
