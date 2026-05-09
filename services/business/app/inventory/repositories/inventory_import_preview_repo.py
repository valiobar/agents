from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.financial.repositories.financial_utils import bson_to_decimal, decimal_to_bson
from app.inventory.models import (
    ImportPreviewStatus,
    InventoryImportPreviewInDB,
    InventoryImportPreviewLine,
)


class InventoryImportPreviewRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.collection = db["inventory_import_previews"]

    def _to_model(self, doc: dict[str, Any]) -> InventoryImportPreviewInDB:
        converted = bson_to_decimal(doc)
        lines = [InventoryImportPreviewLine(**line) for line in converted.get("lines", [])]
        return InventoryImportPreviewInDB(
            id=str(converted["_id"]),
            user_id=converted["user_id"],
            company_id=converted["company_id"],
            document_id=converted.get("document_id"),
            source_type=converted["source_type"],
            status=converted.get("status", "draft"),
            lines=lines,
            created_at=converted.get("created_at", datetime.now(timezone.utc)),
            updated_at=converted.get("updated_at", datetime.now(timezone.utc)),
        )

    @staticmethod
    def _serialize_lines(lines: list[InventoryImportPreviewLine]) -> list[dict[str, Any]]:
        return [decimal_to_bson(line.model_dump(mode="python")) for line in lines]

    async def create(
        self,
        user_id: str,
        company_id: str,
        document_id: str | None,
        source_type: str,
        lines: list[InventoryImportPreviewLine],
    ) -> InventoryImportPreviewInDB:
        now = datetime.now(timezone.utc)
        doc: dict[str, Any] = {
            "user_id": user_id,
            "company_id": company_id,
            "document_id": document_id,
            "source_type": source_type,
            "status": "draft",
            "lines": self._serialize_lines(lines),
            "created_at": now,
            "updated_at": now,
        }
        result = await self.collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return self._to_model(doc)

    async def get_by_id(self, user_id: str, preview_id: str) -> InventoryImportPreviewInDB | None:
        if not ObjectId.is_valid(preview_id):
            return None
        doc = await self.collection.find_one({"_id": ObjectId(preview_id), "user_id": user_id})
        return self._to_model(doc) if doc else None

    async def require_draft(self, user_id: str, preview_id: str) -> InventoryImportPreviewInDB | None:
        if not ObjectId.is_valid(preview_id):
            return None
        doc = await self.collection.find_one(
            {"_id": ObjectId(preview_id), "user_id": user_id, "status": "draft"}
        )
        return self._to_model(doc) if doc else None

    async def update_lines(
        self,
        user_id: str,
        preview_id: str,
        lines: list[InventoryImportPreviewLine],
    ) -> InventoryImportPreviewInDB | None:
        if not ObjectId.is_valid(preview_id):
            return None

        doc = await self.collection.find_one_and_update(
            {"_id": ObjectId(preview_id), "user_id": user_id, "status": "draft"},
            {
                "$set": {
                    "lines": self._serialize_lines(lines),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return self._to_model(doc) if doc else None

    async def mark_confirmed(self, user_id: str, preview_id: str) -> InventoryImportPreviewInDB | None:
        return await self._mark_status(user_id, preview_id, "confirmed")

    async def mark_cancelled(self, user_id: str, preview_id: str) -> InventoryImportPreviewInDB | None:
        return await self._mark_status(user_id, preview_id, "cancelled")

    async def _mark_status(
        self,
        user_id: str,
        preview_id: str,
        next_status: ImportPreviewStatus,
    ) -> InventoryImportPreviewInDB | None:
        if not ObjectId.is_valid(preview_id):
            return None
        doc = await self.collection.find_one_and_update(
            {"_id": ObjectId(preview_id), "user_id": user_id, "status": "draft"},
            {"$set": {"status": next_status, "updated_at": datetime.now(timezone.utc)}},
            return_document=ReturnDocument.AFTER,
        )
        return self._to_model(doc) if doc else None

    async def list_by_company(
        self,
        user_id: str,
        company_id: str,
        status: ImportPreviewStatus | None,
        limit: int,
        offset: int,
    ) -> list[InventoryImportPreviewInDB]:
        query = self._build_list_query(user_id, company_id, status)
        cursor = self.collection.find(query).sort("created_at", -1).skip(offset).limit(limit)
        return [self._to_model(doc) async for doc in cursor]

    @staticmethod
    def _build_list_query(
        user_id: str,
        company_id: str,
        status: ImportPreviewStatus | None,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {"user_id": user_id, "company_id": company_id}
        if status:
            query["status"] = status
        return query

    async def count_by_filters(
        self,
        user_id: str,
        company_id: str,
        status: ImportPreviewStatus | None,
    ) -> int:
        return int(await self.collection.count_documents(self._build_list_query(user_id, company_id, status)))
