from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import BulkWriteError

from app.models.shared.usage import UsageEventCreate, UsageEventInDB


class UsageRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.collection = db["usage_events"]

    def _to_model(self, doc: Mapping[str, Any]) -> UsageEventInDB:
        payload = dict(doc)
        return UsageEventInDB(
            id=str(payload.pop("_id")),
            **payload,
        )

    async def insert_many(self, events: list[UsageEventCreate]) -> int:
        if not events:
            return 0

        docs = [
            {
                **event.model_dump(mode="python"),
                "idempotency_key": event.idempotency_key,
            }
            for event in events
        ]

        try:
            result = await self.collection.insert_many(docs, ordered=False)
            return len(result.inserted_ids)
        except BulkWriteError as exc:
            details = exc.details or {}
            write_errors = details.get("writeErrors", [])
            if write_errors and all(error.get("code") == 11000 for error in write_errors):
                return int(details.get("nInserted", 0))
            raise
