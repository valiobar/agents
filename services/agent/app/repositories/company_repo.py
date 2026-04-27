from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.models.company import CompanyCreate, CompanyInDB, CompanyUpdate


class CompanyRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.collection = db["companies"]

    def _to_model(self, doc: dict) -> CompanyInDB:
        return CompanyInDB(
            id=str(doc["_id"]),
            **{k: v for k, v in doc.items() if k != "_id"},
        )

    async def _unset_other_defaults(self, user_id: str) -> None:
        await self.collection.update_many({"user_id": user_id}, {"$set": {"is_default": False}})

    async def create(self, user_id: str, payload: CompanyCreate) -> CompanyInDB:
        now = datetime.now(timezone.utc)
        doc = payload.model_dump(mode="python")
        if payload.is_default:
            await self._unset_other_defaults(user_id)
        doc.update({"user_id": user_id, "created_at": now, "updated_at": now})
        result = await self.collection.insert_one(doc)
        return self._to_model({**doc, "_id": result.inserted_id})

    async def list_by_user(self, user_id: str, limit: int, offset: int) -> list[CompanyInDB]:
        cursor = (
            self.collection.find({"user_id": user_id})
            .sort("created_at", -1)
            .skip(offset)
            .limit(limit)
        )
        return [self._to_model(doc) async for doc in cursor]

    async def get_by_id(self, user_id: str, company_id: str) -> CompanyInDB | None:
        if not ObjectId.is_valid(company_id):
            return None
        doc = await self.collection.find_one({"_id": ObjectId(company_id), "user_id": user_id})
        return self._to_model(doc) if doc else None

    async def update(self, user_id: str, company_id: str, payload: CompanyUpdate) -> CompanyInDB | None:
        if not ObjectId.is_valid(company_id):
            return None

        update = payload.model_dump(exclude_unset=True, mode="python")
        if not update:
            return await self.get_by_id(user_id, company_id)

        if update.get("is_default") is True:
            await self._unset_other_defaults(user_id)

        update["updated_at"] = datetime.now(timezone.utc)
        doc = await self.collection.find_one_and_update(
            {"_id": ObjectId(company_id), "user_id": user_id},
            {"$set": update},
            return_document=ReturnDocument.AFTER,
        )
        return self._to_model(doc) if doc else None

    async def delete(self, user_id: str, company_id: str) -> bool:
        if not ObjectId.is_valid(company_id):
            return False
        result = await self.collection.delete_one({"_id": ObjectId(company_id), "user_id": user_id})
        return result.deleted_count == 1

    async def exists(self, user_id: str, company_id: str) -> bool:
        if not ObjectId.is_valid(company_id):
            return False
        doc = await self.collection.find_one(
            {"_id": ObjectId(company_id), "user_id": user_id},
            projection={"_id": 1},
        )
        return doc is not None

