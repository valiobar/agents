from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import OperationFailure

from app.config import settings

client: AsyncIOMotorClient | None = None


async def connect_db() -> None:
    global client
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client[settings.db_name]
    await db["agents"].create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await db["agents"].create_index([("user_id", ASCENDING), ("name", ASCENDING)])
    await db["agents"].create_index(
        [("user_id", ASCENDING), ("agent_type", ASCENDING), ("company_id", ASCENDING), ("created_at", DESCENDING)]
    )
    await db["agents"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("created_at", DESCENDING)]
    )
    await db["conversations"].create_index(
        [("user_id", ASCENDING), ("agent_id", ASCENDING), ("updated_at", DESCENDING)]
    )
    await db["conversations"].create_index(
        [("user_id", ASCENDING), ("agent_id", ASCENDING), ("company_id", ASCENDING), ("updated_at", DESCENDING)]
    )
    await db["conversations"].create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await db["usage_events"].create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await db["usage_events"].create_index(
        [("user_id", ASCENDING), ("provider", ASCENDING), ("model", ASCENDING), ("created_at", DESCENDING)]
    )
    await db["usage_events"].create_index([("conversation_id", ASCENDING), ("created_at", ASCENDING)])
    await db["usage_events"].create_index([("agent_id", ASCENDING), ("created_at", DESCENDING)])
    await db["usage_events"].create_index([("idempotency_key", ASCENDING)], unique=True)

    await db["invoices"].create_index(
        [("user_id", ASCENDING), ("status", ASCENDING), ("issue_date", DESCENDING)]
    )
    await db["invoices"].create_index([("user_id", ASCENDING), ("issue_date", DESCENDING)])
    await db["invoices"].create_index([("user_id", ASCENDING), ("counterparty", ASCENDING)])
    await db["invoices"].create_index([("user_id", ASCENDING), ("items.category", ASCENDING)])
    try:
        await db["invoices"].drop_index("user_id_1_invoice_number_1")
    except OperationFailure:
        pass

    await db["invoices"].create_index([("user_id", ASCENDING), ("company_id", ASCENDING), ("issue_date", DESCENDING)])
    await db["invoices"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("status", ASCENDING), ("issue_date", DESCENDING)]
    )
    await db["invoices"].create_index([("user_id", ASCENDING), ("company_id", ASCENDING), ("partner_id", ASCENDING)])
    await db["invoices"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("invoice_number", ASCENDING)],
        unique=True,
    )

    await db["expenses"].create_index(
        [("user_id", ASCENDING), ("category", ASCENDING), ("expense_date", DESCENDING)]
    )
    await db["expenses"].create_index([("user_id", ASCENDING), ("expense_date", DESCENDING)])
    await db["expenses"].create_index([("user_id", ASCENDING), ("counterparty", ASCENDING)])
    await db["expenses"].create_index([("user_id", ASCENDING), ("deductible", ASCENDING)])

    await db["companies"].create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await db["companies"].create_index([("user_id", ASCENDING), ("registration_number", ASCENDING)], unique=True)
    await db["companies"].create_index([("user_id", ASCENDING), ("is_default", ASCENDING)])

    await db["partners"].create_index([("user_id", ASCENDING), ("company_id", ASCENDING), ("name", ASCENDING)])
    await db["partners"].create_index([("user_id", ASCENDING), ("company_id", ASCENDING), ("kind", ASCENDING)])
    await db["partners"].create_index(
        [("user_id", ASCENDING), ("company_id", ASCENDING), ("registration_number", ASCENDING)],
        unique=True,
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
