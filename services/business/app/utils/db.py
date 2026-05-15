from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import OperationFailure

from app.common.search import build_search_text, normalize_search_key, normalize_search_text
from app.config import settings

client: AsyncIOMotorClient | None = None
EXISTS_OPERATOR = "$exists"


async def connect_db() -> None:
    global client
    client = AsyncIOMotorClient(settings.mongodb_url)
    await client.admin.command("ping")
    await backfill_search_normalized_fields()
    await ensure_indexes()


async def backfill_search_normalized_fields() -> None:
    db = get_database()
    await _backfill_party_search_fields(db, "companies")
    await _backfill_party_search_fields(db, "partners")
    await _backfill_counterparty_search_fields(db, "invoices")
    await _backfill_counterparty_search_fields(db, "expenses")


async def _backfill_party_search_fields(db: AsyncIOMotorDatabase, collection_name: str) -> None:
    collection = db[collection_name]
    missing_filter = {
        "$or": [
            {"name_normalized": {EXISTS_OPERATOR: False}},
            {"registration_number_normalized": {EXISTS_OPERATOR: False}},
            {"vat_number_normalized": {EXISTS_OPERATOR: False}},
            {"search_text": {EXISTS_OPERATOR: False}},
        ]
    }
    projection = {"name": 1, "registration_number": 1, "vat_number": 1}

    async for doc in collection.find(missing_filter, projection):
        name_normalized = normalize_search_text(doc.get("name"))
        registration_number_normalized = normalize_search_key(doc.get("registration_number"))
        vat_number_normalized = normalize_search_key(doc.get("vat_number"))
        search_text = build_search_text(name_normalized, registration_number_normalized, vat_number_normalized)
        await collection.update_one(
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


async def _backfill_counterparty_search_fields(db: AsyncIOMotorDatabase, collection_name: str) -> None:
    collection = db[collection_name]
    async for doc in collection.find(
        {"counterparty_normalized": {EXISTS_OPERATOR: False}},
        {"counterparty": 1},
    ):
        await collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {"counterparty_normalized": normalize_search_text(doc.get("counterparty"))}},
        )


async def ensure_indexes() -> None:
    db = get_database()
    await db["invoices"].create_index(
        [("user_id", ASCENDING), ("status", ASCENDING), ("issue_date", DESCENDING)]
    )
    await db["invoices"].create_index([("user_id", ASCENDING), ("issue_date", DESCENDING)])
    await db["invoices"].create_index([("user_id", ASCENDING), ("counterparty", ASCENDING)])
    await db["invoices"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("counterparty_normalized", ASCENDING)]
    )
    await db["invoices"].create_index([("user_id", ASCENDING), ("items.category", ASCENDING)])
    try:
        await db["invoices"].drop_index("user_id_1_invoice_number_1")
    except OperationFailure:
        pass

    await db["invoices"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("issue_date", DESCENDING)]
    )
    await db["invoices"].create_index(
        [
            ("user_id", ASCENDING),
            ("company_id", ASCENDING),
            ("status", ASCENDING),
            ("issue_date", DESCENDING),
        ]
    )
    await db["invoices"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("partner_id", ASCENDING)]
    )
    await db["invoices"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("invoice_number", ASCENDING)],
        unique=True,
    )

    await db["expenses"].create_index(
        [("user_id", ASCENDING), ("category", ASCENDING), ("expense_date", DESCENDING)]
    )
    await db["expenses"].create_index([("user_id", ASCENDING), ("expense_date", DESCENDING)])
    await db["expenses"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("expense_date", DESCENDING)]
    )
    await db["expenses"].create_index(
        [
            ("user_id", ASCENDING),
            ("company_id", ASCENDING),
            ("category", ASCENDING),
            ("expense_date", DESCENDING),
        ]
    )
    await db["expenses"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("partner_id", ASCENDING)]
    )
    await db["expenses"].create_index([("user_id", ASCENDING), ("counterparty", ASCENDING)])
    await db["expenses"].create_index([("user_id", ASCENDING), ("counterparty_normalized", ASCENDING)])
    await db["expenses"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("counterparty_normalized", ASCENDING)]
    )
    await db["expenses"].create_index([("user_id", ASCENDING), ("deductible", ASCENDING)])

    await db["companies"].create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await db["companies"].create_index([("user_id", ASCENDING), ("name", ASCENDING)])
    await db["companies"].create_index([("user_id", ASCENDING), ("name_normalized", ASCENDING)])
    await db["companies"].create_index([("user_id", ASCENDING), ("registration_number", ASCENDING)], unique=True)
    await db["companies"].create_index(
        [("user_id", ASCENDING), ("registration_number_normalized", ASCENDING)],
        unique=True,
    )
    await db["companies"].create_index([("user_id", ASCENDING), ("is_default", ASCENDING)])

    await db["partners"].create_index([("user_id", ASCENDING), ("company_id", ASCENDING), ("name", ASCENDING)])
    await db["partners"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("name_normalized", ASCENDING)]
    )
    await db["partners"].create_index([("user_id", ASCENDING), ("company_id", ASCENDING), ("kind", ASCENDING)])
    await db["partners"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("registration_number", ASCENDING)],
        unique=True,
    )
    await db["partners"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("registration_number_normalized", ASCENDING)],
        unique=True,
    )
    await db["partners"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("vat_number_normalized", ASCENDING)],
        sparse=True,
    )

    await db["inventory_items"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("sku", ASCENDING)],
        unique=True,
    )
    await db["inventory_items"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("barcode", ASCENDING)],
        sparse=True,
    )
    await db["inventory_items"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("is_active", ASCENDING), ("name", ASCENDING)]
    )
    await db["inventory_items"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("category", ASCENDING)]
    )
    await db["inventory_items"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("aliases", ASCENDING)]
    )
    await db["inventory_items"].create_index(
        [
            ("name", "text"),
            ("description", "text"),
            ("category", "text"),
            ("aliases", "text"),
            ("search_text", "text"),
        ],
        weights={"name": 10, "aliases": 8, "category": 5, "search_text": 3, "description": 1},
        name="inventory_items_text_search",
        default_language="none",
    )

    await db["inventory_locations"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("name", ASCENDING)]
    )
    await db["inventory_locations"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("is_default", ASCENDING)]
    )

    await db["stock_movements"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("item_id", ASCENDING), ("occurred_at", DESCENDING)]
    )
    await db["stock_movements"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("location_id", ASCENDING)]
    )
    await db["stock_movements"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("movement_type", ASCENDING)]
    )
    # Keep source idempotency for generated movements, but do not index manual movements
    # that omit source fields.
    stock_movement_source_index_name = "stock_movements_source_unique"
    stock_movement_source_index_keys = [
        ("user_id", ASCENDING),
        ("source_type", ASCENDING),
        ("source_id", ASCENDING),
        ("source_line_id", ASCENDING),
    ]
    stock_movement_source_index_partial = {
        "source_type": {EXISTS_OPERATOR: True},
        "source_id": {EXISTS_OPERATOR: True},
        "source_line_id": {EXISTS_OPERATOR: True},
    }
    try:
        await db["stock_movements"].create_index(
            stock_movement_source_index_keys,
            unique=True,
            partialFilterExpression=stock_movement_source_index_partial,
            name=stock_movement_source_index_name,
        )
    except OperationFailure:
        # Existing deployments may already have this index as sparse+unique.
        # Recreate it as partial+unique to avoid null duplicate-key collisions.
        try:
            await db["stock_movements"].drop_index(stock_movement_source_index_name)
        except OperationFailure:
            pass
        await db["stock_movements"].create_index(
            stock_movement_source_index_keys,
            unique=True,
            partialFilterExpression=stock_movement_source_index_partial,
            name=stock_movement_source_index_name,
        )

    await db["inventory_import_previews"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)]
    )
    await db["inventory_import_previews"].create_index(
        [("user_id", ASCENDING), ("document_id", ASCENDING)],
        sparse=True,
    )


def close_db() -> None:
    global client
    if client is not None:
        client.close()
        client = None


def get_database() -> AsyncIOMotorDatabase:
    if client is None:
        raise RuntimeError("Database client is not initialized")
    return client[settings.db_name]
