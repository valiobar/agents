from __future__ import annotations

import re
from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.common.search import normalize_search_text
from app.financial.models import FinancialSummaryRequest, InvoiceFilters, InvoiceInDB
from app.financial.repositories.financial_utils import (
    bson_to_decimal,
    date_to_datetime_range,
    decimal_to_bson,
    document_timestamps,
)


class InvoiceRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.collection = db["invoices"]
        self.counters = db["counters"]

    def _to_model(self, doc: dict) -> InvoiceInDB:
        doc = bson_to_decimal(doc)
        issue_dt = doc["issue_date"]
        due_dt = doc.get("due_date")
        due_date = due_dt.date() if isinstance(due_dt, datetime) else due_dt
        created_at, updated_at = document_timestamps(doc, fallback_date_field="issue_date")
        return InvoiceInDB(
            id=str(doc["_id"]),
            user_id=doc["user_id"],
            company_id=doc.get("company_id"),
            partner_id=doc.get("partner_id"),
            invoice_number=doc["invoice_number"],
            counterparty=doc.get("counterparty"),
            supplier_snapshot=doc.get("supplier_snapshot"),
            recipient_snapshot=doc.get("recipient_snapshot"),
            issue_date=issue_dt.date() if isinstance(issue_dt, datetime) else issue_dt,
            due_date=due_date,
            tax_event_date=(
                doc["tax_event_date"].date()
                if isinstance(doc.get("tax_event_date"), datetime)
                else doc.get("tax_event_date")
            ),
            place_of_supply=doc.get("place_of_supply"),
            payment_method=doc.get("payment_method"),
            bank_name=doc.get("bank_name"),
            bank_bic=doc.get("bank_bic"),
            bank_iban=doc.get("bank_iban"),
            amount_in_words=doc.get("amount_in_words"),
            currency=doc["currency"],
            items=doc["items"],
            subtotal=doc["subtotal"],
            vat_total=doc["vat_total"],
            total=doc["total"],
            status=doc["status"],
            vat_reason=doc.get("vat_reason"),
            recipient_name=doc.get("recipient_name"),
            compiler_name=doc.get("compiler_name"),
            original_label=doc.get("original_label"),
            notes=doc.get("notes"),
            created_at=created_at,
            updated_at=updated_at,
        )

    async def next_invoice_number(self, user_id: str, company_id: str, year: int) -> str:
        key = f"invoice:{user_id}:{company_id}:{year}"
        doc = await self.counters.find_one_and_update(
            {"_id": key},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        seq = int(doc["seq"])
        return f"INV-{year}-{seq:05d}"

    async def create(self, doc: dict) -> InvoiceInDB:
        now = datetime.now(timezone.utc)
        if "issue_date" in doc and not isinstance(doc["issue_date"], datetime):
            doc["issue_date"] = date_to_datetime_range(doc["issue_date"])
        if "tax_event_date" in doc and not isinstance(doc["tax_event_date"], datetime):
            doc["tax_event_date"] = date_to_datetime_range(doc["tax_event_date"])
        if doc.get("due_date") and not isinstance(doc["due_date"], datetime):
            doc["due_date"] = date_to_datetime_range(doc["due_date"])

        doc["counterparty_normalized"] = normalize_search_text(doc.get("counterparty"))
        doc.update({"created_at": now, "updated_at": now})
        stored = decimal_to_bson(doc)
        result = await self.collection.insert_one(stored)
        doc["_id"] = result.inserted_id
        return self._to_model(doc)

    def _apply_date_filter(self, query: dict, filters: InvoiceFilters) -> None:
        if not filters.date_from and not filters.date_to:
            return

        query["issue_date"] = {}
        if filters.date_from:
            query["issue_date"]["$gte"] = date_to_datetime_range(filters.date_from)
        if filters.date_to:
            query["issue_date"]["$lte"] = date_to_datetime_range(filters.date_to, end_of_day=True)

    def _apply_amount_filter(self, query: dict, filters: InvoiceFilters) -> None:
        if filters.amount_min is None and filters.amount_max is None:
            return

        query["total"] = {}
        if filters.amount_min is not None:
            query["total"]["$gte"] = decimal_to_bson(filters.amount_min)
        if filters.amount_max is not None:
            query["total"]["$lte"] = decimal_to_bson(filters.amount_max)

    def _build_filter(self, user_id: str, filters: InvoiceFilters) -> dict:
        query: dict = {"user_id": user_id}
        if filters.company_id:
            query["company_id"] = filters.company_id
        if filters.partner_id:
            query["partner_id"] = filters.partner_id
        if filters.status:
            query["status"] = filters.status
        if filters.counterparty:
            normalized_counterparty = normalize_search_text(filters.counterparty)
            if normalized_counterparty:
                escaped_counterparty = re.escape(normalized_counterparty)
                query["$or"] = [
                    {"counterparty_normalized": normalized_counterparty},
                    {"counterparty_normalized": {"$regex": f"^{escaped_counterparty}"}},
                    {"counterparty_normalized": {"$regex": escaped_counterparty}},
                ]
        if filters.category:
            query["items.category"] = filters.category
        self._apply_date_filter(query, filters)
        self._apply_amount_filter(query, filters)
        return query

    async def list_by_user(
        self, user_id: str, filters: InvoiceFilters, limit: int, offset: int
    ) -> list[InvoiceInDB]:
        cursor = (
            self.collection.find(self._build_filter(user_id, filters))
            .sort("issue_date", -1)
            .skip(offset)
            .limit(limit)
        )
        return [self._to_model(doc) async for doc in cursor]

    async def count_by_user(self, user_id: str, filters: InvoiceFilters) -> int:
        return int(await self.collection.count_documents(self._build_filter(user_id, filters)))

    async def get_by_id(self, user_id: str, invoice_id: str) -> InvoiceInDB | None:
        if not ObjectId.is_valid(invoice_id):
            return None
        doc = await self.collection.find_one({"_id": ObjectId(invoice_id), "user_id": user_id})
        return self._to_model(doc) if doc else None

    async def count_by_company(self, user_id: str, company_id: str) -> int:
        return int(await self.collection.count_documents({"user_id": user_id, "company_id": company_id}))

    async def count_by_partner(self, user_id: str, company_id: str, partner_id: str) -> int:
        return int(
            await self.collection.count_documents(
                {"user_id": user_id, "company_id": company_id, "partner_id": partner_id}
            )
        )

    async def update_status_or_metadata(
        self, user_id: str, invoice_id: str, update: dict
    ) -> InvoiceInDB | None:
        if not ObjectId.is_valid(invoice_id):
            return None

        if "issue_date" in update and update["issue_date"] and not isinstance(update["issue_date"], datetime):
            update["issue_date"] = date_to_datetime_range(update["issue_date"])
        if "due_date" in update and update["due_date"] and not isinstance(update["due_date"], datetime):
            update["due_date"] = date_to_datetime_range(update["due_date"])
        if "counterparty" in update:
            update["counterparty_normalized"] = normalize_search_text(update.get("counterparty"))

        update["updated_at"] = datetime.now(timezone.utc)
        doc = await self.collection.find_one_and_update(
            {"_id": ObjectId(invoice_id), "user_id": user_id},
            {"$set": decimal_to_bson(update)},
            return_document=ReturnDocument.AFTER,
        )
        return self._to_model(doc) if doc else None

    def _summary_match(self, user_id: str, request: FinancialSummaryRequest) -> dict:
        match: dict = {"user_id": user_id}
        if request.company_id:
            match["company_id"] = request.company_id
        if request.partner_id:
            match["partner_id"] = request.partner_id
        if request.date_from or request.date_to:
            match["issue_date"] = {}
            if request.date_from:
                match["issue_date"]["$gte"] = date_to_datetime_range(request.date_from)
            if request.date_to:
                match["issue_date"]["$lte"] = date_to_datetime_range(request.date_to, end_of_day=True)
        return match

    def _group_key(self, group_by: str | None) -> object:
        if group_by == "counterparty":
            return "$counterparty"
        if group_by == "month":
            return {"$dateToString": {"format": "%Y-%m", "date": "$issue_date"}}
        if group_by == "category":
            return {"$ifNull": ["$items.category", "uncategorized"]}
        return "all"

    async def aggregate_summary(self, user_id: str, request: FinancialSummaryRequest) -> list[dict]:
        match = self._summary_match(user_id, request)
        group_id = {
            "key": self._group_key(request.group_by),
            "currency": "$currency",
        }

        if request.group_by == "category":
            pipeline = [
                {"$match": match},
                {"$unwind": "$items"},
                {
                    "$group": {
                        "_id": group_id,
                        "invoice_total": {"$sum": "$items.total"},
                    }
                },
                {"$sort": {"_id": 1}},
            ]
        else:
            pipeline = [
                {"$match": match},
                {"$group": {"_id": group_id, "invoice_total": {"$sum": "$total"}}},
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
