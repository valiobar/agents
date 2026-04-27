from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.models.document import DocumentCreate, DocumentInDB, DocumentStatus, DocumentUpdate


class DocumentRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["documents"]

    def _to_model(self, doc: dict[str, Any]) -> DocumentInDB:
        doc["_id"] = str(doc["_id"])
        return DocumentInDB.model_validate(doc)

    def _to_object_id(self, document_id: str) -> ObjectId | None:
        try:
            return ObjectId(document_id)
        except Exception:
            return None

    async def create(self, user_id: str, document: DocumentCreate) -> DocumentInDB:
        now = datetime.now(UTC)
        payload = document.model_dump()
        payload.update(
            {
                "user_id": user_id,
                "status": DocumentStatus.PROCESSING,
                "chunk_count": 0,
                "created_at": now,
                "updated_at": now,
            }
        )
        result = await self.collection.insert_one(payload)
        payload["_id"] = result.inserted_id
        return self._to_model(payload)

    async def get_by_id(self, document_id: str, user_id: str) -> DocumentInDB | None:
        oid = self._to_object_id(document_id)
        if oid is None:
            return None
        doc = await self.collection.find_one(
            {"_id": oid, "user_id": user_id, "status": {"$ne": DocumentStatus.DELETED}}
        )
        return self._to_model(doc) if doc else None

    async def find_by_hash(self, user_id: str, company_id: str, content_hash: str) -> DocumentInDB | None:
        doc = await self.collection.find_one(
            {
                "user_id": user_id,
                "company_id": company_id,
                "content_hash": content_hash,
                "status": DocumentStatus.READY,
            }
        )
        return self._to_model(doc) if doc else None

    async def list_by_user_company(
        self, user_id: str, company_id: str, limit: int, offset: int
    ) -> list[DocumentInDB]:
        cursor = (
            self.collection.find(
                {
                    "user_id": user_id,
                    "company_id": company_id,
                    "status": {"$ne": DocumentStatus.DELETED},
                }
            )
            .sort("created_at", -1)
            .skip(offset)
            .limit(limit)
        )
        return [self._to_model(doc) async for doc in cursor]

    async def update(self, document_id: str, user_id: str, update: DocumentUpdate) -> DocumentInDB | None:
        oid = self._to_object_id(document_id)
        if oid is None:
            return None

        payload = update.model_dump(exclude_unset=True)
        if not payload:
            return await self.get_by_id(document_id=document_id, user_id=user_id)

        payload["updated_at"] = datetime.now(UTC)
        doc = await self.collection.find_one_and_update(
            {"_id": oid, "user_id": user_id},
            {"$set": payload},
            return_document=ReturnDocument.AFTER,
        )
        return self._to_model(doc) if doc else None

    async def mark_deleted(self, document_id: str, user_id: str) -> DocumentInDB | None:
        oid = self._to_object_id(document_id)
        if oid is None:
            return None
        doc = await self.collection.find_one_and_update(
            {"_id": oid, "user_id": user_id},
            {
                "$set": {
                    "status": DocumentStatus.DELETED,
                    "updated_at": datetime.now(UTC),
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return self._to_model(doc) if doc else None

    async def hard_delete(self, document_id: str, user_id: str) -> bool:
        oid = self._to_object_id(document_id)
        if oid is None:
            return False
        result = await self.collection.delete_one({"_id": oid, "user_id": user_id})
        return result.deleted_count == 1

