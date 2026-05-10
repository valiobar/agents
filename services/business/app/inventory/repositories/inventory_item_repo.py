from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.financial.repositories.financial_utils import bson_to_decimal, decimal_to_bson
from app.inventory.models import (
    InventoryCategoryListResponse,
    InventoryCategorySummary,
    InventoryItemCreate,
    InventoryItemFilters,
    InventoryItemInDB,
    InventoryItemUpdate,
    InventoryItemStatusCounts,
    InventorySearchMatch,
    SearchMatchReason,
)

_MONGO_REGEX = "$regex"
_MONGO_OPTIONS = "$options"
_MONGO_META = "$meta"
_MONGO_OR = "$or"
_MONGO_MATCH = "$match"
_UNICODE_DASHES = {
    ord("\u2010"): "-",
    ord("\u2011"): "-",
    ord("\u2012"): "-",
    ord("\u2013"): "-",
    ord("\u2014"): "-",
    ord("\u2015"): "-",
    ord("\u2212"): "-",
}


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).translate(_UNICODE_DASHES)
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Cf")
    normalized = normalized.lower().strip()
    return re.sub(r"\s+", " ", normalized)


def _looks_like_identifier(query: str) -> bool:
    return any(char.isdigit() for char in query) or "-" in query


def _search_text_token_regex(value: str) -> str:
    return rf"(^| ){re.escape(value)}($| )"


def _search_text_token_prefix_regex(value: str) -> str:
    return rf"(^| ){re.escape(value)}"


def _build_search_text(
    name: str,
    sku: str,
    barcode: str | None,
    category: str | None,
    description: str | None,
    aliases: list[str] | None,
) -> str:
    parts = [name, sku]
    if barcode:
        parts.append(barcode)
    if category:
        parts.append(category)
    if description:
        parts.append(description)
    if aliases:
        parts.extend(alias for alias in aliases if alias)
    return normalize_text(" ".join(parts))


class InventoryItemRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.collection = db["inventory_items"]

    def _to_model(self, doc: dict) -> InventoryItemInDB:
        doc = bson_to_decimal(doc)
        owner_user_id = doc["user_id"]
        return InventoryItemInDB(
            id=str(doc["_id"]),
            user_id=owner_user_id,
            created_by_user_id=doc.get("created_by_user_id", owner_user_id),
            updated_by_user_id=doc.get("updated_by_user_id", owner_user_id),
            company_id=doc["company_id"],
            sku=doc["sku"],
            name=doc["name"],
            description=doc.get("description"),
            category=doc.get("category"),
            barcode=doc.get("barcode"),
            aliases=doc.get("aliases", []),
            search_text=doc.get("search_text", ""),
            unit=doc["unit"],
            selling_price=doc.get("selling_price"),
            reorder_point=doc.get("reorder_point"),
            target_stock_level=doc.get("target_stock_level"),
            supplier_partner_id=doc.get("supplier_partner_id"),
            is_active=doc.get("is_active", True),
            created_at=doc.get("created_at", datetime.now(timezone.utc)),
            updated_at=doc.get("updated_at", datetime.now(timezone.utc)),
        )

    def _to_search_match(
        self,
        doc: dict,
        reason: SearchMatchReason,
        confidence: float,
    ) -> InventorySearchMatch:
        doc = bson_to_decimal(doc)
        return InventorySearchMatch(
            item_id=str(doc["_id"]),
            name=doc["name"],
            description=doc.get("description"),
            sku=doc.get("sku"),
            category=doc.get("category"),
            unit=doc["unit"],
            selling_price=doc.get("selling_price"),
            confidence=round(confidence, 2),
            match_reason=reason,
        )

    async def create(
        self,
        user_id: str,
        payload: InventoryItemCreate,
        *,
        changed_by_user_id: str | None = None,
    ) -> InventoryItemInDB:
        now = datetime.now(timezone.utc)
        doc = payload.model_dump(mode="python")
        doc["user_id"] = user_id
        actor_user_id = changed_by_user_id or user_id
        doc["created_by_user_id"] = actor_user_id
        doc["updated_by_user_id"] = actor_user_id
        doc["search_text"] = _build_search_text(
            payload.name,
            payload.sku,
            payload.barcode,
            payload.category,
            payload.description,
            payload.aliases,
        )
        doc["created_at"] = now
        doc["updated_at"] = now
        result = await self.collection.insert_one(decimal_to_bson(doc))
        doc["_id"] = result.inserted_id
        return self._to_model(doc)

    async def get_by_id(self, user_id: str, company_id: str, item_id: str) -> InventoryItemInDB | None:
        if not ObjectId.is_valid(item_id):
            return None
        doc = await self.collection.find_one(
            {
                "_id": ObjectId(item_id),
                "user_id": user_id,
                "company_id": company_id,
            }
        )
        return self._to_model(doc) if doc else None

    async def get_many_by_ids(
        self,
        user_id: str,
        company_id: str,
        item_ids: list[str],
    ) -> dict[str, InventoryItemInDB]:
        object_ids = [ObjectId(value) for value in item_ids if ObjectId.is_valid(value)]
        if not object_ids:
            return {}
        cursor = self.collection.find(
            {
                "_id": {"$in": object_ids},
                "user_id": user_id,
                "company_id": company_id,
            }
        )
        items = [self._to_model(doc) async for doc in cursor]
        return {item.id: item for item in items}

    async def find_by_sku(self, user_id: str, company_id: str, sku: str) -> InventoryItemInDB | None:
        doc = await self.collection.find_one(
            {
                "user_id": user_id,
                "company_id": company_id,
                "sku": sku,
            }
        )
        return self._to_model(doc) if doc else None

    async def find_by_barcode(
        self,
        user_id: str,
        company_id: str,
        barcode: str,
    ) -> InventoryItemInDB | None:
        doc = await self.collection.find_one(
            {
                "user_id": user_id,
                "company_id": company_id,
                "barcode": barcode,
            }
        )
        return self._to_model(doc) if doc else None

    async def update(
        self,
        user_id: str,
        company_id: str,
        item_id: str,
        payload: InventoryItemUpdate,
        *,
        changed_by_user_id: str | None = None,
    ) -> InventoryItemInDB | None:
        if not ObjectId.is_valid(item_id):
            return None

        update = payload.model_dump(exclude_unset=True, mode="python")
        if not update:
            return await self.get_by_id(user_id, company_id, item_id)

        current = await self.get_by_id(user_id, company_id, item_id)
        if current is None:
            return None

        name = update.get("name") or current.name
        barcode = update.get("barcode", current.barcode)
        category = update.get("category", current.category)
        description = update.get("description", current.description)
        aliases = update.get("aliases")
        if aliases is None:
            aliases = current.aliases

        update["search_text"] = _build_search_text(
            name,
            current.sku,
            barcode,
            category,
            description,
            aliases,
        )
        update["updated_at"] = datetime.now(timezone.utc)
        update["updated_by_user_id"] = changed_by_user_id or user_id

        doc = await self.collection.find_one_and_update(
            {"_id": ObjectId(item_id), "user_id": user_id, "company_id": company_id},
            {"$set": decimal_to_bson(update)},
            return_document=ReturnDocument.AFTER,
        )
        return self._to_model(doc) if doc else None

    async def list_by_company(
        self,
        user_id: str,
        filters: InventoryItemFilters,
        limit: int,
        offset: int,
    ) -> list[InventoryItemInDB]:
        query = self._build_list_query(user_id, filters)
        cursor = self.collection.find(query).sort("name", 1).skip(offset).limit(limit)
        return [self._to_model(doc) async for doc in cursor]

    def _build_list_query(self, user_id: str, filters: InventoryItemFilters) -> dict[str, object]:
        query: dict[str, object] = {"user_id": user_id, "company_id": filters.company_id}
        if filters.category:
            query["category"] = filters.category
        if filters.is_active is not None:
            query["is_active"] = filters.is_active
        if filters.search:
            normalized_search = normalize_text(filters.search)
            raw_search = filters.search.strip()
            if normalized_search and raw_search:
                escaped_search = re.escape(raw_search)
                escaped_normalized = re.escape(normalized_search)
                query[_MONGO_OR] = [
                    {"name": {_MONGO_REGEX: escaped_search, _MONGO_OPTIONS: "i"}},
                    {"sku": {_MONGO_REGEX: escaped_search, _MONGO_OPTIONS: "i"}},
                    {"search_text": {_MONGO_REGEX: escaped_normalized, _MONGO_OPTIONS: "i"}},
                ]
        if filters.sku:
            query["sku"] = filters.sku
        if filters.barcode:
            query["barcode"] = filters.barcode
        return query

    async def count_by_filters(self, user_id: str, filters: InventoryItemFilters) -> int:
        return int(await self.collection.count_documents(self._build_list_query(user_id, filters)))

    async def count_by_company(self, user_id: str, company_id: str) -> int:
        return int(await self.collection.count_documents({"user_id": user_id, "company_id": company_id}))

    async def count_statuses(self, user_id: str, company_id: str) -> InventoryItemStatusCounts:
        pipeline = [
            {_MONGO_MATCH: {"user_id": user_id, "company_id": company_id}},
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "active": {"$sum": {"$cond": [{"$eq": ["$is_active", True]}, 1, 0]}},
                }
            },
        ]
        docs = await self.collection.aggregate(pipeline).to_list(1)
        if not docs:
            return InventoryItemStatusCounts(total=0, active=0, inactive=0)
        row = docs[0]
        total = int(row.get("total", 0))
        active = int(row.get("active", 0))
        return InventoryItemStatusCounts(total=total, active=active, inactive=max(total - active, 0))

    async def count_categories(self, user_id: str, company_id: str) -> int:
        pipeline = [
            {_MONGO_MATCH: {"user_id": user_id, "company_id": company_id}},
            {
                "$group": {
                    "_id": {"$toLower": {"$trim": {"input": {"$ifNull": ["$category", ""]}}}},
                }
            },
            {_MONGO_MATCH: {"_id": {"$ne": ""}}},
            {"$count": "total"},
        ]
        docs = await self.collection.aggregate(pipeline).to_list(1)
        if not docs:
            return 0
        return int(docs[0].get("total", 0))

    async def list_categories(self, user_id: str, company_id: str) -> InventoryCategoryListResponse:
        pipeline = [
            {_MONGO_MATCH: {"user_id": user_id, "company_id": company_id}},
            {"$addFields": {"normalized_category": {"$trim": {"input": {"$ifNull": ["$category", ""]}}}}},
            {
                "$facet": {
                    "categorized": [
                        {_MONGO_MATCH: {"normalized_category": {"$ne": ""}}},
                        {"$group": {
                            "_id": {"$toLower": "$normalized_category"},
                            "item_count": {"$sum": 1},
                            "active_item_count": {
                                "$sum": {"$cond": [{"$eq": ["$is_active", True]}, 1, 0]},
                            },
                        }},
                        {"$sort": {"_id": 1}},
                    ],
                    "uncategorized": [
                        {_MONGO_MATCH: {"normalized_category": ""}},
                        {"$count": "count"},
                    ],
                }
            },
        ]
        docs = await self.collection.aggregate(pipeline).to_list(1)
        if not docs:
            return InventoryCategoryListResponse(
                total_category_count=0,
                uncategorized_item_count=0,
                categories=[],
            )

        result = docs[0]
        categories = [
            InventoryCategorySummary(
                category=str(row["_id"]),
                item_count=int(row.get("item_count", 0)),
                active_item_count=int(row.get("active_item_count", 0)),
            )
            for row in result.get("categorized", [])
        ]
        uncategorized_rows = result.get("uncategorized", [])
        uncategorized_count = int(uncategorized_rows[0].get("count", 0)) if uncategorized_rows else 0
        return InventoryCategoryListResponse(
            total_category_count=len(categories),
            uncategorized_item_count=uncategorized_count,
            categories=categories,
        )

    async def find_exact_identifier_or_alias(
        self,
        user_id: str,
        company_id: str,
        query: str,
        limit: int = 20,
    ) -> list[InventorySearchMatch]:
        base = {"user_id": user_id, "company_id": company_id, "is_active": True}
        normalized_query = normalize_text(query)
        if not normalized_query:
            return []

        exact = f"^{re.escape(normalized_query)}$"
        doc = await self.collection.find_one(
            {**base, "sku": {_MONGO_REGEX: exact, _MONGO_OPTIONS: "i"}}
        )
        if doc:
            return [self._to_search_match(doc, "sku", 1.0)]

        doc = await self.collection.find_one(
            {**base, "barcode": {_MONGO_REGEX: exact, _MONGO_OPTIONS: "i"}}
        )
        if doc:
            return [self._to_search_match(doc, "barcode", 1.0)]

        if _looks_like_identifier(normalized_query):
            doc = await self.collection.find_one(
                {
                    **base,
                    "search_text": {
                        _MONGO_REGEX: _search_text_token_regex(normalized_query),
                        _MONGO_OPTIONS: "i",
                    },
                }
            )
            if doc:
                return [self._to_search_match(doc, "text", 0.95)]

        docs = (
            await self.collection.find(
                {
                    **base,
                    "aliases": {
                        "$elemMatch": {
                            _MONGO_REGEX: exact,
                            _MONGO_OPTIONS: "i",
                        }
                    },
                }
            )
            .limit(limit)
            .to_list(limit)
        )
        if docs:
            return [self._to_search_match(doc, "alias", 0.95) for doc in docs]

        return []

    async def search_items(
        self,
        user_id: str,
        company_id: str,
        query: str,
        limit: int,
    ) -> list[InventorySearchMatch]:
        exact = await self.find_exact_identifier_or_alias(user_id, company_id, query)
        if exact:
            return exact[:limit]

        base = {"user_id": user_id, "company_id": company_id, "is_active": True}
        normalized = normalize_text(query)
        prefix = await self.find_identifier_prefix_matches(base, normalized, limit)
        if prefix:
            return prefix

        docs = (
            await self.collection.find(
                {**base, "$text": {"$search": normalized}},
                {"score": {_MONGO_META: "textScore"}},
            )
            .sort([("score", {_MONGO_META: "textScore"})])
            .to_list(limit)
        )
        if docs:
            max_score = max(doc.get("score", 1) for doc in docs)
            divisor = max(max_score, 1)
            return [
                self._to_search_match(doc, "text", min(doc.get("score", 0) / divisor, 1.0))
                for doc in docs
            ]

        return await self.find_identifier_prefix_matches(base, normalized, limit)

    async def find_identifier_prefix_matches(
        self,
        base: dict,
        normalized: str,
        limit: int,
    ) -> list[InventorySearchMatch]:
        if not normalized:
            return []

        escaped = re.escape(normalized)
        or_filters: list[dict] = [
            {"sku": {_MONGO_REGEX: f"^{escaped}", _MONGO_OPTIONS: "i"}},
            {"name": {_MONGO_REGEX: f"^{escaped}", _MONGO_OPTIONS: "i"}},
            {
                "search_text": {
                    _MONGO_REGEX: _search_text_token_prefix_regex(normalized),
                    _MONGO_OPTIONS: "i",
                }
            }
        ]

        # Keep explicit identifier prefix matching for SKU/barcode/aliases, but allow
        # plain text token-prefix fallback for queries like "INT".
        if _looks_like_identifier(normalized):
            or_filters.extend(
                [
                    {"barcode": {_MONGO_REGEX: f"^{escaped}", _MONGO_OPTIONS: "i"}},
                    {
                        "aliases": {
                            "$elemMatch": {
                                _MONGO_REGEX: f"^{escaped}",
                                _MONGO_OPTIONS: "i",
                            }
                        }
                    },
                ]
            )

        docs = await self.collection.find({**base, _MONGO_OR: or_filters}).limit(limit).to_list(limit)
        return [self._to_search_match(doc, "prefix", 0.9) for doc in docs]

    async def find_best_match(
        self,
        user_id: str,
        company_id: str,
        sku: str | None,
        barcode: str | None,
        description: str,
    ) -> InventoryItemInDB | None:
        base = {"user_id": user_id, "company_id": company_id}
        if sku:
            doc = await self.collection.find_one({**base, "sku": sku})
            if doc:
                return self._to_model(doc)

        if barcode:
            doc = await self.collection.find_one({**base, "barcode": barcode})
            if doc:
                return self._to_model(doc)

        normalized = normalize_text(description)
        doc = await self.collection.find_one(
            {**base, "is_active": True, "$text": {"$search": normalized}},
            {"score": {_MONGO_META: "textScore"}},
        )
        if doc and doc.get("score", 0) > 2.0:
            return self._to_model(doc)
        return None
