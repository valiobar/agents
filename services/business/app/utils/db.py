from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import OperationFailure

from app.config import settings

client: AsyncIOMotorClient | None = None


async def connect_db() -> None:
    global client
    client = AsyncIOMotorClient(settings.mongodb_url)
    await client.admin.command("ping")
    await ensure_indexes()


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
    exists_operator = "$exists"
    stock_movement_source_index_name = "stock_movements_source_unique"
    stock_movement_source_index_keys = [
        ("user_id", ASCENDING),
        ("source_type", ASCENDING),
        ("source_id", ASCENDING),
        ("source_line_id", ASCENDING),
    ]
    stock_movement_source_index_partial = {
        "source_type": {exists_operator: True},
        "source_id": {exists_operator: True},
        "source_line_id": {exists_operator: True},
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
