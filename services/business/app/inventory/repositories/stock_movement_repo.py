from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.financial.repositories.financial_utils import bson_to_decimal, decimal_to_bson
from app.inventory.models import (
    InventoryMovementSummaryRow,
    ReorderReportRow,
    StockByCategoryRow,
    StockLevelFilters,
    StockMovementCreate,
    StockMovementFilters,
    StockMovementInDB,
)

_MONGO_MATCH = "$match"
_MONGO_GROUP = "$group"


class StockMovementRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.collection = db["stock_movements"]

    def _to_model(self, doc: dict) -> StockMovementInDB:
        doc = bson_to_decimal(doc)
        owner_user_id = doc["user_id"]
        return StockMovementInDB(
            id=str(doc["_id"]),
            user_id=owner_user_id,
            performed_by_user_id=doc.get("performed_by_user_id", owner_user_id),
            company_id=doc["company_id"],
            item_id=doc["item_id"],
            location_id=doc["location_id"],
            movement_type=doc["movement_type"],
            quantity_delta=doc["quantity_delta"],
            reason=doc.get("reason"),
            source_type=doc.get("source_type"),
            source_id=doc.get("source_id"),
            source_line_id=doc.get("source_line_id"),
            occurred_at=doc.get("occurred_at", datetime.now(timezone.utc)),
            created_at=doc.get("created_at", datetime.now(timezone.utc)),
        )

    async def insert(
        self,
        user_id: str,
        payload: StockMovementCreate,
        *,
        performed_by_user_id: str | None = None,
    ) -> StockMovementInDB:
        now = datetime.now(timezone.utc)
        doc = payload.model_dump(mode="python", exclude_none=True)
        doc["user_id"] = user_id
        doc["performed_by_user_id"] = performed_by_user_id or user_id
        doc["occurred_at"] = now
        doc["created_at"] = now

        result = await self.collection.insert_one(decimal_to_bson(doc))
        doc["_id"] = result.inserted_id
        return self._to_model(doc)

    async def list_by_filters(
        self,
        user_id: str,
        filters: StockMovementFilters,
        limit: int,
        offset: int,
    ) -> list[StockMovementInDB]:
        query = self._build_list_query(user_id, filters)
        cursor = self.collection.find(query).sort("occurred_at", -1).skip(offset).limit(limit)
        return [self._to_model(doc) async for doc in cursor]

    def _build_list_query(self, user_id: str, filters: StockMovementFilters) -> dict[str, Any]:
        query: dict[str, Any] = {"user_id": user_id, "company_id": filters.company_id}
        if filters.item_id:
            query["item_id"] = filters.item_id
        if filters.location_id:
            query["location_id"] = filters.location_id
        if filters.movement_type:
            query["movement_type"] = filters.movement_type
        return query

    async def count_by_filters(self, user_id: str, filters: StockMovementFilters) -> int:
        return int(await self.collection.count_documents(self._build_list_query(user_id, filters)))

    async def aggregate_available_quantities(
        self,
        user_id: str,
        company_id: str,
        item_ids: list[str],
    ) -> dict[str, Decimal]:
        if not item_ids:
            return {}

        pipeline = [
            {_MONGO_MATCH: {"user_id": user_id, "company_id": company_id, "item_id": {"$in": item_ids}}},
            {_MONGO_GROUP: {"_id": "$item_id", "total": {"$sum": "$quantity_delta"}}},
        ]

        results: dict[str, Decimal] = {}
        async for doc in self.collection.aggregate(pipeline):
            converted = bson_to_decimal(doc)
            results[converted["_id"]] = converted["total"]
        return results

    async def aggregate_levels_by_location(
        self,
        user_id: str,
        filters: StockLevelFilters,
    ) -> tuple[list[dict[str, str | Decimal]], int, int]:
        match: dict[str, Any] = {"user_id": user_id, "company_id": filters.company_id}
        if filters.item_id:
            match["item_id"] = filters.item_id
        if filters.location_id:
            match["location_id"] = filters.location_id

        quantity_match: dict[str, Decimal] = {}
        if filters.min_available_quantity is not None:
            quantity_match["$gte"] = filters.min_available_quantity
        if filters.max_available_quantity is not None:
            quantity_match["$lte"] = filters.max_available_quantity
        pipeline = [
            {_MONGO_MATCH: match},
            {
                _MONGO_GROUP: {
                    "_id": {"item_id": "$item_id", "location_id": "$location_id"},
                    "total": {"$sum": "$quantity_delta"},
                }
            },
        ]
        if quantity_match:
            pipeline.append({_MONGO_MATCH: {"total": decimal_to_bson(quantity_match)}})
        pipeline.append(
            {
                "$facet": {
                    "rows": [
                        {"$sort": {"total": -1 if filters.sort_direction == "desc" else 1}},
                        {"$skip": filters.offset},
                        {"$limit": filters.limit},
                    ],
                    "count": [{"$count": "total"}],
                    "items": [{"$group": {"_id": "$_id.item_id"}}, {"$count": "total"}],
                }
            }
        )
        docs = await self.collection.aggregate(pipeline).to_list(1)
        if not docs:
            return [], 0, 0

        results: list[dict[str, str | Decimal]] = []
        facet = docs[0]
        for doc in facet.get("rows", []):
            converted = bson_to_decimal(doc)
            results.append(
                {
                    "item_id": converted["_id"]["item_id"],
                    "location_id": converted["_id"]["location_id"],
                    "available_quantity": converted["total"],
                }
            )
        count_rows = facet.get("count", [])
        item_rows = facet.get("items", [])
        total_count = int(count_rows[0]["total"]) if count_rows else 0
        unique_item_count = int(item_rows[0]["total"]) if item_rows else 0
        return results, total_count, unique_item_count

    async def reorder_report(
        self,
        user_id: str,
        company_id: str,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[ReorderReportRow], int]:
        pipeline = [
            {_MONGO_MATCH: {"user_id": user_id, "company_id": company_id}},
            {
                _MONGO_GROUP: {
                    "_id": {"item_id": "$item_id", "location_id": "$location_id"},
                    "available_quantity": {"$sum": "$quantity_delta"},
                }
            },
            {
                "$lookup": {
                    "from": "inventory_items",
                    "let": {"item_id": "$_id.item_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": [{"$toString": "$_id"}, "$$item_id"]},
                                        {"$eq": ["$user_id", user_id]},
                                        {"$eq": ["$company_id", company_id]},
                                    ]
                                }
                            }
                        }
                    ],
                    "as": "item",
                }
            },
            {"$unwind": "$item"},
            {
                "$match": {
                    "item.reorder_point": {"$ne": None},
                    "$expr": {"$lte": ["$available_quantity", "$item.reorder_point"]},
                }
            },
            {
                "$lookup": {
                    "from": "inventory_locations",
                    "let": {"location_id": "$_id.location_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": [{"$toString": "$_id"}, "$$location_id"]},
                                        {"$eq": ["$user_id", user_id]},
                                        {"$eq": ["$company_id", company_id]},
                                    ]
                                }
                            }
                        }
                    ],
                    "as": "location",
                }
            },
            {"$unwind": "$location"},
            {
                "$project": {
                    "_id": 0,
                    "item_id": "$_id.item_id",
                    "item_name": "$item.name",
                    "sku": "$item.sku",
                    "location_id": "$_id.location_id",
                    "location_name": "$location.name",
                    "available_quantity": "$available_quantity",
                    "reorder_point": "$item.reorder_point",
                    "target_stock_level": "$item.target_stock_level",
                    "supplier_partner_id": "$item.supplier_partner_id",
                    "suggested_reorder_quantity": {
                        "$cond": [
                            {"$and": [{"$ne": ["$item.target_stock_level", None]}, {"$gt": ["$item.target_stock_level", "$available_quantity"]}]},
                            {"$subtract": ["$item.target_stock_level", "$available_quantity"]},
                            None,
                        ]
                    },
                }
            },
            {
                "$facet": {
                    "rows": [
                        {"$sort": {"available_quantity": 1, "item_name": 1}},
                        {"$skip": offset},
                        {"$limit": limit},
                    ],
                    "count": [{"$count": "total"}],
                }
            },
        ]
        docs = await self.collection.aggregate(pipeline).to_list(1)
        if not docs:
            return [], 0
        facet = docs[0]
        rows: list[ReorderReportRow] = []
        for row in facet.get("rows", []):
            converted = bson_to_decimal(row)
            rows.append(ReorderReportRow.model_validate(converted))
        count_rows = facet.get("count", [])
        total = int(count_rows[0]["total"]) if count_rows else 0
        return rows, total

    async def stock_by_category(
        self,
        user_id: str,
        company_id: str,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[StockByCategoryRow], int]:
        pipeline = [
            {_MONGO_MATCH: {"user_id": user_id, "company_id": company_id}},
            {
                "$lookup": {
                    "from": "stock_movements",
                    "let": {"item_id": {"$toString": "$_id"}},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$item_id", "$$item_id"]},
                                        {"$eq": ["$user_id", user_id]},
                                        {"$eq": ["$company_id", company_id]},
                                    ]
                                }
                            }
                        },
                        {_MONGO_GROUP: {"_id": None, "available_quantity": {"$sum": "$quantity_delta"}}},
                    ],
                    "as": "stock",
                }
            },
            {
                "$addFields": {
                    "normalized_category": {
                        "$trim": {"input": {"$ifNull": ["$category", ""]}},
                    },
                    "available_quantity": {"$ifNull": [{"$arrayElemAt": ["$stock.available_quantity", 0]}, 0]},
                }
            },
            {
                _MONGO_GROUP: {
                    "_id": {
                        "$cond": [
                            {"$eq": ["$normalized_category", ""]},
                            None,
                            {"$toLower": "$normalized_category"},
                        ]
                    },
                    "item_count": {"$sum": 1},
                    "total_available_quantity": {"$sum": "$available_quantity"},
                }
            },
            {
                "$facet": {
                    "rows": [
                        {"$sort": {"total_available_quantity": -1, "_id": 1}},
                        {"$skip": offset},
                        {"$limit": limit},
                    ],
                    "count": [{"$count": "total"}],
                }
            },
        ]
        docs = await self.collection.database["inventory_items"].aggregate(pipeline).to_list(1)
        if not docs:
            return [], 0
        facet = docs[0]
        rows: list[StockByCategoryRow] = []
        for row in facet.get("rows", []):
            converted = bson_to_decimal(row)
            rows.append(
                StockByCategoryRow(
                    category=converted.get("_id"),
                    item_count=int(converted.get("item_count", 0)),
                    total_available_quantity=converted.get("total_available_quantity", Decimal("0")),
                )
            )
        count_rows = facet.get("count", [])
        total = int(count_rows[0]["total"]) if count_rows else 0
        return rows, total

    async def negative_stock_levels(
        self,
        user_id: str,
        company_id: str,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, str | Decimal]], int]:
        pipeline = [
            {_MONGO_MATCH: {"user_id": user_id, "company_id": company_id}},
            {
                _MONGO_GROUP: {
                    "_id": {"item_id": "$item_id", "location_id": "$location_id"},
                    "total": {"$sum": "$quantity_delta"},
                }
            },
            {_MONGO_MATCH: {"total": {"$lt": Decimal("0")}}},
            {
                "$facet": {
                    "rows": [
                        {"$sort": {"total": 1}},
                        {"$skip": offset},
                        {"$limit": limit},
                    ],
                    "count": [{"$count": "total"}],
                }
            },
        ]
        docs = await self.collection.aggregate(decimal_to_bson(pipeline)).to_list(1)
        if not docs:
            return [], 0
        facet = docs[0]
        rows: list[dict[str, str | Decimal]] = []
        for row in facet.get("rows", []):
            converted = bson_to_decimal(row)
            rows.append(
                {
                    "item_id": converted["_id"]["item_id"],
                    "location_id": converted["_id"]["location_id"],
                    "available_quantity": converted["total"],
                }
            )
        count_rows = facet.get("count", [])
        total = int(count_rows[0]["total"]) if count_rows else 0
        return rows, total

    async def count_low_and_negative_stock(self, user_id: str, company_id: str) -> tuple[int, int]:
        pipeline = [
            {_MONGO_MATCH: {"user_id": user_id, "company_id": company_id}},
            {
                _MONGO_GROUP: {
                    "_id": {"item_id": "$item_id", "location_id": "$location_id"},
                    "available_quantity": {"$sum": "$quantity_delta"},
                }
            },
            {
                "$lookup": {
                    "from": "inventory_items",
                    "let": {"item_id": "$_id.item_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": [{"$toString": "$_id"}, "$$item_id"]},
                                        {"$eq": ["$user_id", user_id]},
                                        {"$eq": ["$company_id", company_id]},
                                    ]
                                }
                            }
                        }
                    ],
                    "as": "item",
                }
            },
            {"$unwind": "$item"},
            {
                "$facet": {
                    "low": [
                        {
                            "$match": {
                                "item.reorder_point": {"$ne": None},
                                "$expr": {"$lte": ["$available_quantity", "$item.reorder_point"]},
                            }
                        },
                        {"$group": {"_id": "$_id.item_id"}},
                        {"$count": "total"},
                    ],
                    "negative": [
                        {"$match": {"$expr": {"$lt": ["$available_quantity", Decimal("0")]}}},
                        {"$group": {"_id": "$_id.item_id"}},
                        {"$count": "total"},
                    ],
                }
            },
        ]
        docs = await self.collection.aggregate(decimal_to_bson(pipeline)).to_list(1)
        if not docs:
            return 0, 0
        facet = docs[0]
        low_rows = facet.get("low", [])
        negative_rows = facet.get("negative", [])
        low_total = int(low_rows[0]["total"]) if low_rows else 0
        negative_total = int(negative_rows[0]["total"]) if negative_rows else 0
        return low_total, negative_total

    async def summarize_movements(
        self,
        user_id: str,
        company_id: str,
        *,
        group_by: Literal["day", "item", "movement_type"],
        limit: int,
    ) -> list[InventoryMovementSummaryRow]:
        if group_by == "day":
            label_expr: Any = {
                "$dateToString": {"date": "$occurred_at", "format": "%Y-%m-%d", "timezone": "UTC"}
            }
        elif group_by == "item":
            label_expr = "$item_id"
        else:
            label_expr = "$movement_type"

        pipeline = [
            {_MONGO_MATCH: {"user_id": user_id, "company_id": company_id}},
            {
                _MONGO_GROUP: {
                    "_id": label_expr,
                    "movement_count": {"$sum": 1},
                    "total_quantity_delta": {"$sum": "$quantity_delta"},
                }
            },
            {"$sort": {"movement_count": -1, "_id": 1}},
            {"$limit": limit},
        ]
        rows: list[InventoryMovementSummaryRow] = []
        async for row in self.collection.aggregate(pipeline):
            converted = bson_to_decimal(row)
            rows.append(
                InventoryMovementSummaryRow(
                    label=str(converted.get("_id") or "unknown"),
                    movement_count=int(converted.get("movement_count", 0)),
                    total_quantity_delta=converted.get("total_quantity_delta", Decimal("0")),
                )
            )
        return rows

    async def has_source_movement(
        self,
        user_id: str,
        source_type: str,
        source_id: str,
        source_line_id: str,
    ) -> bool:
        doc = await self.collection.find_one(
            {
                "user_id": user_id,
                "source_type": source_type,
                "source_id": source_id,
                "source_line_id": source_line_id,
            },
            projection={"_id": 1},
        )
        return doc is not None

    async def count_by_source(self, user_id: str, source_id: str) -> int:
        return int(await self.collection.count_documents({"user_id": user_id, "source_id": source_id}))
