from __future__ import annotations

from asyncio import sleep
from datetime import UTC, datetime
from pathlib import Path
import sys
import unittest

from pymongo.errors import BulkWriteError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.shared.usage import UsageEventCreate
from app.repositories.usage_repo import UsageRepository


def fake_event() -> UsageEventCreate:
    now = datetime.now(UTC)
    return UsageEventCreate(
        user_id="user-1",
        agent_id="agent-1",
        conversation_id="conversation-1",
        provider="openai",
        model="gpt-4.1-mini",
        run_id="run-1",
        llm_call_index=1,
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        stream_chunks=1,
        stream_chars=5,
        started_at=now,
        completed_at=now,
        duration_ms=100,
        created_at=now,
    )


class FakeInsertManyResult:
    def __init__(self, inserted_ids: list[str]) -> None:
        self.inserted_ids = inserted_ids


class FakeCollection:
    def __init__(self, *, duplicate_error: BulkWriteError | None = None) -> None:
        self.duplicate_error = duplicate_error
        self.calls = 0

    async def insert_many(self, docs, ordered: bool):
        await sleep(0)
        self.calls += 1
        if self.duplicate_error is not None:
            raise self.duplicate_error
        return FakeInsertManyResult([f"id-{idx}" for idx, _ in enumerate(docs, start=1)])


class FakeDB:
    def __init__(self, collection: FakeCollection) -> None:
        self.collection = collection

    def __getitem__(self, name: str):
        if name != "usage_events":
            raise KeyError(name)
        return self.collection


class UsageRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_insert_many_returns_zero_for_empty_input(self) -> None:
        collection = FakeCollection()
        repo = UsageRepository(FakeDB(collection))

        inserted = await repo.insert_many([])

        self.assertEqual(inserted, 0)
        self.assertEqual(collection.calls, 0)

    async def test_insert_many_returns_n_inserted_for_duplicate_key_bulk_write(self) -> None:
        duplicate_error = BulkWriteError(
            {
                "writeErrors": [
                    {"index": 1, "code": 11000, "errmsg": "dup key"},
                    {"index": 2, "code": 11000, "errmsg": "dup key"},
                ],
                "nInserted": 1,
            }
        )
        collection = FakeCollection(duplicate_error=duplicate_error)
        repo = UsageRepository(FakeDB(collection))

        inserted = await repo.insert_many([fake_event(), fake_event(), fake_event()])

        self.assertEqual(inserted, 1)
        self.assertEqual(collection.calls, 1)

    async def test_insert_many_reraises_non_duplicate_bulk_write_errors(self) -> None:
        mixed_error = BulkWriteError(
            {
                "writeErrors": [
                    {"index": 0, "code": 11000, "errmsg": "dup key"},
                    {"index": 1, "code": 121, "errmsg": "validation failure"},
                ],
                "nInserted": 1,
            }
        )
        collection = FakeCollection(duplicate_error=mixed_error)
        repo = UsageRepository(FakeDB(collection))

        with self.assertRaises(BulkWriteError):
            await repo.insert_many([fake_event(), fake_event()])


if __name__ == "__main__":
    unittest.main()
