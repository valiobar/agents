from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.common.search import build_search_text, normalize_search_key, normalize_search_text
from app.partner.models import PartnerCreate, PartnerInDB, PartnerResolveRequest, PartnerUpdate

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

    def _build_company_filters(
        self,
        user_id: str,
        company_id: str,
        kind: str | None,
        query: str | None,
    ) -> dict:
        filters: dict = {"user_id": user_id, "company_id": company_id}
        if kind:
            filters["kind"] = kind
        if query:
            normalized_text = normalize_search_text(query)
            normalized_key = normalize_search_key(query)
            clauses: list[dict[str, Any]] = []
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
                filters["$or"] = clauses
        return filters

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

    async def create(self, user_id: str, payload: PartnerCreate) -> PartnerInDB:
        now = datetime.now(timezone.utc)
        doc = payload.model_dump(mode="python")
        doc.update(self._build_search_fields(payload.name, payload.registration_number, payload.vat_number))
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
        filters = self._build_company_filters(user_id, company_id, kind, query)
        cursor = (
            self.collection.find(filters)
            .sort("created_at", -1)
            .skip(offset)
            .limit(limit)
        )
        return [self._to_model(doc) async for doc in cursor]

    async def count_by_company_filters(
        self,
        user_id: str,
        company_id: str,
        kind: str | None,
        query: str | None,
    ) -> int:
        filters = self._build_company_filters(user_id, company_id, kind, query)
        return int(await self.collection.count_documents(filters))

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
        candidates = await self.resolve_candidates(
            user_id=user_id,
            payload=PartnerResolveRequest(
                company_id=company_id,
                partner_id=identifier,
                registration_number=identifier,
                vat_number=identifier,
                name=identifier,
                limit=2,
            ),
        )
        return candidates[0] if len(candidates) == 1 else None

    async def update(self, user_id: str, partner_id: str, payload: PartnerUpdate) -> PartnerInDB | None:
        if not ObjectId.is_valid(partner_id):
            return None

        update = payload.model_dump(exclude_unset=True, mode="python")
        if not update:
            return await self.get_by_id(user_id, partner_id)

        if {"name", "registration_number", "vat_number"} & set(update):
            current = await self.get_by_id(user_id, partner_id)
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

        update["updated_at"] = datetime.now(timezone.utc)
        doc = await self.collection.find_one_and_update(
            {"_id": ObjectId(partner_id), "user_id": user_id},
            {"$set": update},
            return_document=ReturnDocument.AFTER,
        )
        return self._to_model(doc) if doc else None

    async def resolve_candidates(self, user_id: str, payload: PartnerResolveRequest) -> list[PartnerInDB]:
        filters: dict[str, Any] = {"user_id": user_id, "company_id": payload.company_id}
        if payload.kind:
            if payload.kind == "both":
                filters["kind"] = "both"
            else:
                filters["kind"] = {"$in": [payload.kind, "both"]}

        clauses = self._build_resolve_clauses(payload)
        if not clauses:
            return []

        filters["$or"] = clauses
        cursor = self.collection.find(filters).sort("updated_at", -1).limit(payload.limit * 3)
        return [self._to_model(doc) async for doc in cursor]

    def _build_resolve_clauses(self, payload: PartnerResolveRequest) -> list[dict[str, Any]]:
        clauses: list[dict[str, Any]] = []
        if payload.partner_id and ObjectId.is_valid(payload.partner_id):
            clauses.append({"_id": ObjectId(payload.partner_id)})

        normalized_registration_number = normalize_search_key(payload.registration_number)
        if normalized_registration_number:
            clauses.append({"registration_number_normalized": normalized_registration_number})

        normalized_vat_number = normalize_search_key(payload.vat_number)
        if normalized_vat_number:
            clauses.append({"vat_number_normalized": normalized_vat_number})

        name_key = normalize_search_text(payload.name)
        if name_key:
            escaped_name_key = re.escape(name_key)
            clauses.extend(
                [
                    {"name_normalized": name_key},
                    {"name_normalized": {_MONGO_REGEX: f"^{escaped_name_key}"}},
                    {"search_text": {_MONGO_REGEX: escaped_name_key}},
                ]
            )
        return clauses

    async def delete(self, user_id: str, partner_id: str) -> bool:
        if not ObjectId.is_valid(partner_id):
            return False
        result = await self.collection.delete_one({"_id": ObjectId(partner_id), "user_id": user_id})
        return result.deleted_count == 1

    async def count_by_company(self, user_id: str, company_id: str) -> int:
        return int(await self.collection.count_documents({"user_id": user_id, "company_id": company_id}))
