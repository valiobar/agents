from __future__ import annotations

import asyncio
import os

from motor.motor_asyncio import AsyncIOMotorClient

from services.business.app.common.search import build_search_text, normalize_search_key, normalize_search_text


async def _backfill_companies(db) -> None:
    companies = db["companies"]
    async for doc in companies.find({}, {"_id": 1, "name": 1, "registration_number": 1, "vat_number": 1}):
        name_normalized = normalize_search_text(doc.get("name"))
        registration_number_normalized = normalize_search_key(doc.get("registration_number"))
        vat_number_normalized = normalize_search_key(doc.get("vat_number"))
        search_text = build_search_text(name_normalized, registration_number_normalized, vat_number_normalized)
        await companies.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "name_normalized": name_normalized,
                    "registration_number_normalized": registration_number_normalized,
                    "vat_number_normalized": vat_number_normalized,
                    "search_text": search_text,
                }
            },
        )


async def _backfill_partners(db) -> None:
    partners = db["partners"]
    async for doc in partners.find({}, {"_id": 1, "name": 1, "registration_number": 1, "vat_number": 1}):
        name_normalized = normalize_search_text(doc.get("name"))
        registration_number_normalized = normalize_search_key(doc.get("registration_number"))
        vat_number_normalized = normalize_search_key(doc.get("vat_number"))
        search_text = build_search_text(name_normalized, registration_number_normalized, vat_number_normalized)
        await partners.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "name_normalized": name_normalized,
                    "registration_number_normalized": registration_number_normalized,
                    "vat_number_normalized": vat_number_normalized,
                    "search_text": search_text,
                }
            },
        )


async def _backfill_invoices(db) -> None:
    invoices = db["invoices"]
    async for doc in invoices.find({}, {"_id": 1, "counterparty": 1}):
        await invoices.update_one(
            {"_id": doc["_id"]},
            {"$set": {"counterparty_normalized": normalize_search_text(doc.get("counterparty"))}},
        )


async def _backfill_expenses(db) -> None:
    expenses = db["expenses"]
    async for doc in expenses.find({}, {"_id": 1, "counterparty": 1}):
        await expenses.update_one(
            {"_id": doc["_id"]},
            {"$set": {"counterparty_normalized": normalize_search_text(doc.get("counterparty"))}},
        )


async def main() -> None:
    mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017/agents")
    db_name = os.getenv("MONGODB_DB_NAME", "agents")

    client = AsyncIOMotorClient(mongo_url)
    try:
        db = client[db_name]
        await _backfill_companies(db)
        await _backfill_partners(db)
        await _backfill_invoices(db)
        await _backfill_expenses(db)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
