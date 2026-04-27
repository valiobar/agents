from __future__ import annotations

import re
from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.models.partner import PartnerCreate, PartnerInDB, PartnerUpdate

_MONGO_REGEX = "$regex"
_MONGO_OPTIONS = "$options"


class PartnerRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.collection = db["partners"]

    def _to_model(self, doc: dict) -> PartnerInDB:
        return PartnerInDB(
            id=str(doc["_id"]),
            **{k: v for k, v in doc.items() if k != "_id"},
        )

    async def create(self, user_id: str, payload: PartnerCreate) -> PartnerInDB:
        now = datetime.now(timezone.utc)
        doc = payload.model_dump(mode="python")
        doc.update({"user_id": user_id, "created_at": now, "updated_at": now})
        result = await self.collection.insert_one(doc)
        return self._to_model({**doc, "_id": result.inserted_id})

    async def list_by_company(
        self,
        user_id: str,
        company_id: str,
        kind: str | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> list[PartnerInDB]:
        filters: dict = {"user_id": user_id, "company_id": company_id}
        if kind:
            filters["kind"] = kind
        if query:
            q = re.escape(query)
            filters["$or"] = [
                {"name": {_MONGO_REGEX: q, _MONGO_OPTIONS: "i"}},
                {"registration_number": {_MONGO_REGEX: q, _MONGO_OPTIONS: "i"}},
            ]

        cursor = (
            self.collection.find(filters)
            .sort("created_at", -1)
            .skip(offset)
            .limit(limit)
        )
        return [self._to_model(doc) async for doc in cursor]

    async def get_by_id(self, user_id: str, partner_id: str) -> PartnerInDB | None:
        if not ObjectId.is_valid(partner_id):
            return None
        doc = await self.collection.find_one({"_id": ObjectId(partner_id), "user_id": user_id})
        return self._to_model(doc) if doc else None

    async def resolve_by_company_identifier(
        self,
        user_id: str,
        company_id: str,
        identifier: str,
    ) -> PartnerInDB | None:
        partner = await self.get_by_id(user_id, identifier)
        if partner is not None and partner.company_id == company_id:
            return partner

        exact_identifier = f"^{re.escape(identifier)}$"
        doc = await self.collection.find_one(
            {
                "user_id": user_id,
                "company_id": company_id,
                "$or": [
                    {"registration_number": {_MONGO_REGEX: exact_identifier, _MONGO_OPTIONS: "i"}},
                    {"name": {_MONGO_REGEX: exact_identifier, _MONGO_OPTIONS: "i"}},
                ],
            }
        )
        if doc:
            return self._to_model(doc)

        matches = await self.list_by_company(
            user_id=user_id,
            company_id=company_id,
            kind=None,
            query=identifier,
            limit=2,
            offset=0,
        )
        return matches[0] if len(matches) == 1 else None

    async def update(self, user_id: str, partner_id: str, payload: PartnerUpdate) -> PartnerInDB | None:
        if not ObjectId.is_valid(partner_id):
            return None

        update = payload.model_dump(exclude_unset=True, mode="python")
        if not update:
            return await self.get_by_id(user_id, partner_id)

        update["updated_at"] = datetime.now(timezone.utc)
        doc = await self.collection.find_one_and_update(
            {"_id": ObjectId(partner_id), "user_id": user_id},
            {"$set": update},
            return_document=ReturnDocument.AFTER,
        )
        return self._to_model(doc) if doc else None

    async def delete(self, user_id: str, partner_id: str) -> bool:
        if not ObjectId.is_valid(partner_id):
            return False
        result = await self.collection.delete_one({"_id": ObjectId(partner_id), "user_id": user_id})
        return result.deleted_count == 1

