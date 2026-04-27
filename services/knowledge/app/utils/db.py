from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings

client: AsyncIOMotorClient | None = None


async def connect_db() -> None:
    global client
    client = AsyncIOMotorClient(settings.mongodb_url)
    await client.admin.command("ping")
    db = client[settings.db_name]
    await db["documents"].create_index([("user_id", 1), ("company_id", 1), ("created_at", -1)])
    await db["documents"].create_index([("user_id", 1), ("company_id", 1), ("content_hash", 1)])
    await db["documents"].create_index([("user_id", 1), ("company_id", 1), ("status", 1)])


def close_db() -> None:
    global client
    if client is not None:
        client.close()
        client = None


def get_database() -> AsyncIOMotorDatabase:
    if client is None:
        raise RuntimeError("Database client not initialised. Call connect_db() first.")
    return client[settings.db_name]

