from __future__ import annotations

import re
from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.common.search import build_search_text, normalize_search_key, normalize_search_text
from app.company.models import CompanyCreate, CompanyInDB, CompanyUpdate

_MONGO_REGEX = "$regex"


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
        doc.update(self._build_search_fields(payload.name, payload.registration_number, payload.vat_number))
        if payload.is_default:
            await self._unset_other_defaults(user_id)
        doc.update({"user_id": user_id, "created_at": now, "updated_at": now})
        result = await self.collection.insert_one(doc)
        return self._to_model({**doc, "_id": result.inserted_id})

    def _build_search_fields(
        self,
        name: str | None,
        registration_number: str | None,
        vat_number: str | None,
    ) -> dict[str, str | None]:
        name_normalized = normalize_search_text(name)
        registration_number_normalized = normalize_search_key(registration_number)
        vat_number_normalized = normalize_search_key(vat_number)
        search_text = build_search_text(name_normalized, registration_number_normalized, vat_number_normalized)
        return {
            "name_normalized": name_normalized,
            "registration_number_normalized": registration_number_normalized,
            "vat_number_normalized": vat_number_normalized,
            "search_text": search_text,
        }

    def _build_list_filter(self, user_id: str, query: str | None) -> dict[str, object]:
        base: dict[str, object] = {"user_id": user_id}
        if not query or not query.strip():
            return base

        normalized_text = normalize_search_text(query)
        normalized_key = normalize_search_key(query)
        clauses: list[dict[str, object]] = []
        if normalized_text:
            escaped_text = re.escape(normalized_text)
            clauses.extend(
                [
                    {"name_normalized": normalized_text},
                        {"name_normalized": {_MONGO_REGEX: f"^{escaped_text}"}},
                        {"search_text": {_MONGO_REGEX: escaped_text}},
                ]
            )
        if normalized_key:
            escaped_key = re.escape(normalized_key)
            clauses.extend(
                [
                    {"registration_number_normalized": normalized_key},
                        {"registration_number_normalized": {_MONGO_REGEX: f"^{escaped_key}"}},
                    {"vat_number_normalized": normalized_key},
                        {"vat_number_normalized": {_MONGO_REGEX: f"^{escaped_key}"}},
                ]
            )
        if clauses:
            base["$or"] = clauses
        return base

    async def list_by_user(
        self,
        user_id: str,
        *,
        query: str | None,
        limit: int,
        offset: int,
    ) -> list[CompanyInDB]:
        mongo_filter = self._build_list_filter(user_id, query)
        cursor = (
            self.collection.find(mongo_filter)
            .sort("created_at", -1)
            .skip(offset)
            .limit(limit)
        )
        return [self._to_model(doc) async for doc in cursor]

    async def count_by_user(self, user_id: str, *, query: str | None) -> int:
        return int(await self.collection.count_documents(self._build_list_filter(user_id, query)))

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

        if {"name", "registration_number", "vat_number"} & set(update):
            current = await self.get_by_id(user_id, company_id)
            if current is None:
                return None
            next_name = update.get("name")
            next_registration_number = update.get("registration_number")
            next_vat_number = update.get("vat_number")
            update.update(
                self._build_search_fields(
                    next_name if isinstance(next_name, str) else current.name,
                    (
                        next_registration_number
                        if isinstance(next_registration_number, str)
                        else current.registration_number
                    ),
                    next_vat_number if isinstance(next_vat_number, str) else current.vat_number,
                )
            )

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
