from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.inventory.models import (
    InventoryLocationCreate,
    InventoryLocationInDB,
    InventoryLocationUpdate,
)


class InventoryLocationRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.collection = db["inventory_locations"]

    def _to_model(self, doc: dict) -> InventoryLocationInDB:
        return InventoryLocationInDB(
            id=str(doc["_id"]),
            user_id=doc["user_id"],
            company_id=doc["company_id"],
            name=doc["name"],
            description=doc.get("description"),
            is_default=doc.get("is_default", False),
            created_at=doc.get("created_at", datetime.now(timezone.utc)),
            updated_at=doc.get("updated_at", datetime.now(timezone.utc)),
        )

    async def _unset_other_defaults(self, user_id: str, company_id: str) -> None:
        await self.collection.update_many(
            {"user_id": user_id, "company_id": company_id},
            {"$set": {"is_default": False}},
        )

    async def create(self, user_id: str, payload: InventoryLocationCreate) -> InventoryLocationInDB:
        now = datetime.now(timezone.utc)
        doc = payload.model_dump(mode="python")
        if payload.is_default:
            await self._unset_other_defaults(user_id, payload.company_id)

        doc.update(
            {
                "user_id": user_id,
                "created_at": now,
                "updated_at": now,
            }
        )
        result = await self.collection.insert_one(doc)
        return self._to_model({**doc, "_id": result.inserted_id})

    async def get_by_id(
        self,
        user_id: str,
        company_id: str,
        location_id: str,
    ) -> InventoryLocationInDB | None:
        if not ObjectId.is_valid(location_id):
            return None

        doc = await self.collection.find_one(
            {
                "_id": ObjectId(location_id),
                "user_id": user_id,
                "company_id": company_id,
            }
        )
        return self._to_model(doc) if doc else None

    async def get_many_by_ids(
        self,
        user_id: str,
        company_id: str,
        location_ids: list[str],
    ) -> dict[str, InventoryLocationInDB]:
        object_ids = [ObjectId(value) for value in location_ids if ObjectId.is_valid(value)]
        if not object_ids:
            return {}
        cursor = self.collection.find(
            {
                "_id": {"$in": object_ids},
                "user_id": user_id,
                "company_id": company_id,
            }
        )
        locations = [self._to_model(doc) async for doc in cursor]
        return {location.id: location for location in locations}

    async def get_default(self, user_id: str, company_id: str) -> InventoryLocationInDB | None:
        doc = await self.collection.find_one(
            {
                "user_id": user_id,
                "company_id": company_id,
                "is_default": True,
            }
        )
        return self._to_model(doc) if doc else None

    async def update(
        self,
        user_id: str,
        company_id: str,
        location_id: str,
        payload: InventoryLocationUpdate,
    ) -> InventoryLocationInDB | None:
        if not ObjectId.is_valid(location_id):
            return None

        update = payload.model_dump(exclude_unset=True, mode="python")
        if not update:
            return await self.get_by_id(user_id, company_id, location_id)

        if update.get("is_default") is True:
            await self._unset_other_defaults(user_id, company_id)

        update["updated_at"] = datetime.now(timezone.utc)
        doc = await self.collection.find_one_and_update(
            {
                "_id": ObjectId(location_id),
                "user_id": user_id,
                "company_id": company_id,
            },
            {"$set": update},
            return_document=ReturnDocument.AFTER,
        )
        return self._to_model(doc) if doc else None

    async def list_by_company(
        self,
        user_id: str,
        company_id: str,
        limit: int,
        offset: int,
    ) -> list[InventoryLocationInDB]:
        query = self._build_list_query(user_id, company_id)
        cursor = (
            self.collection.find(query)
            .sort("name", 1)
            .skip(offset)
            .limit(limit)
        )
        return [self._to_model(doc) async for doc in cursor]

    @staticmethod
    def _build_list_query(user_id: str, company_id: str) -> dict[str, str]:
        return {"user_id": user_id, "company_id": company_id}

    async def count_by_company(self, user_id: str, company_id: str) -> int:
        return int(await self.collection.count_documents(self._build_list_query(user_id, company_id)))

    async def exists(self, user_id: str, company_id: str, location_id: str) -> bool:
        if not ObjectId.is_valid(location_id):
            return False

        doc = await self.collection.find_one(
            {
                "_id": ObjectId(location_id),
                "user_id": user_id,
                "company_id": company_id,
            },
            projection={"_id": 1},
        )
        return doc is not None
