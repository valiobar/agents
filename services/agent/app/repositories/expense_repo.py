from __future__ import annotations

import re
from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.financial import ExpenseFilters, ExpenseInDB, FinancialSummaryRequest
from app.repositories.financial_utils import (
    bson_to_decimal,
    date_to_datetime_range,
    decimal_to_bson,
    document_timestamps,
)


class ExpenseRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.collection = db["expenses"]

    def _to_model(self, doc: dict) -> ExpenseInDB:
        doc = bson_to_decimal(doc)
        expense_dt = doc["expense_date"]
        created_at, updated_at = document_timestamps(doc, fallback_date_field="expense_date")
        return ExpenseInDB(
            id=str(doc["_id"]),
            user_id=doc["user_id"],
            counterparty=doc["counterparty"],
            expense_date=expense_dt.date() if isinstance(expense_dt, datetime) else expense_dt,
            amount=doc["amount"],
            currency=doc["currency"],
            category=doc["category"],
            description=doc.get("description"),
            deductible=doc["deductible"],
            deductible_rate=doc["deductible_rate"],
            deductible_amount=doc["deductible_amount"],
            source_document_type=doc.get("source_document_type"),
            source_document_id=doc.get("source_document_id"),
            items=doc.get("items"),
            created_at=created_at,
            updated_at=updated_at,
        )

    async def create(self, doc: dict) -> ExpenseInDB:
        now = datetime.now(timezone.utc)
        if "expense_date" in doc and not isinstance(doc["expense_date"], datetime):
            doc["expense_date"] = date_to_datetime_range(doc["expense_date"])

        doc.update({"created_at": now, "updated_at": now})
        result = await self.collection.insert_one(decimal_to_bson(doc))
        doc["_id"] = result.inserted_id
        return self._to_model(doc)

    def _build_filter(self, user_id: str, filters: ExpenseFilters) -> dict:
        query: dict = {"user_id": user_id}
        if filters.category:
            query["category"] = filters.category
        if filters.counterparty:
            query["counterparty"] = {"$regex": re.escape(filters.counterparty), "$options": "i"}
        if filters.deductible is not None:
            query["deductible"] = filters.deductible
        if filters.date_from or filters.date_to:
            query["expense_date"] = {}
            if filters.date_from:
                query["expense_date"]["$gte"] = date_to_datetime_range(filters.date_from)
            if filters.date_to:
                query["expense_date"]["$lte"] = date_to_datetime_range(filters.date_to, end_of_day=True)
        if filters.amount_min is not None or filters.amount_max is not None:
            query["amount"] = {}
            if filters.amount_min is not None:
                query["amount"]["$gte"] = decimal_to_bson(filters.amount_min)
            if filters.amount_max is not None:
                query["amount"]["$lte"] = decimal_to_bson(filters.amount_max)
        return query

    async def list_by_user(
        self, user_id: str, filters: ExpenseFilters, limit: int, offset: int
    ) -> list[ExpenseInDB]:
        cursor = (
            self.collection.find(self._build_filter(user_id, filters))
            .sort("expense_date", -1)
            .skip(offset)
            .limit(limit)
        )
        return [self._to_model(doc) async for doc in cursor]

    async def get_by_id(self, user_id: str, expense_id: str) -> ExpenseInDB | None:
        if not ObjectId.is_valid(expense_id):
            return None
        doc = await self.collection.find_one({"_id": ObjectId(expense_id), "user_id": user_id})
        return self._to_model(doc) if doc else None

    def _summary_match(self, user_id: str, request: FinancialSummaryRequest) -> dict:
        match: dict = {"user_id": user_id}
        if request.date_from or request.date_to:
            match["expense_date"] = {}
            if request.date_from:
                match["expense_date"]["$gte"] = date_to_datetime_range(request.date_from)
            if request.date_to:
                match["expense_date"]["$lte"] = date_to_datetime_range(request.date_to, end_of_day=True)
        return match

    def _group_key(self, group_by: str | None) -> object:
        if group_by == "category":
            return "$category"
        if group_by == "counterparty":
            return "$counterparty"
        if group_by == "month":
            return {"$dateToString": {"format": "%Y-%m", "date": "$expense_date"}}
        return "all"

    async def aggregate_summary(self, user_id: str, request: FinancialSummaryRequest) -> list[dict]:
        pipeline = [
            {"$match": self._summary_match(user_id, request)},
            {
                "$group": {
                    "_id": {
                        "key": self._group_key(request.group_by),
                        "currency": "$currency",
                    },
                    "expense_total": {"$sum": "$amount"},
                    "deductible_expense_total": {"$sum": "$deductible_amount"},
                }
            },
            {"$sort": {"_id": 1}},
        ]
        rows = [bson_to_decimal(row) async for row in self.collection.aggregate(pipeline)]
        for row in rows:
            row_id = row.pop("_id")
            if isinstance(row_id, dict):
                row["key"] = str(row_id.get("key") or "all")
                row["currency"] = str(row_id.get("currency") or "BGN")
            else:
                row["key"] = str(row_id)
                row["currency"] = "BGN"
        return rows

