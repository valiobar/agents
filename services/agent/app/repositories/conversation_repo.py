from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.models.conversation import ConversationInDB, MessageSchema


class ConversationRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.collection = db["conversations"]

    def _to_model(self, doc: dict) -> ConversationInDB:
        raw_messages = doc.get("messages") or []
        messages = [MessageSchema.model_validate(m) for m in raw_messages]
        return ConversationInDB(
            id=str(doc["_id"]),
            user_id=doc["user_id"],
            agent_id=doc["agent_id"],
            company_id=doc.get("company_id"),
            title=doc.get("title"),
            messages=messages,
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )

    async def create(
        self,
        user_id: str,
        agent_id: str,
        company_id: str | None,
        first_message: str | None = None,
    ) -> ConversationInDB:
        now = datetime.now(timezone.utc)
        title = first_message[:80] if first_message else None
        doc: dict = {
            "user_id": user_id,
            "agent_id": agent_id,
            "company_id": company_id,
            "title": title,
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }
        result = await self.collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return self._to_model(doc)

    async def get_by_id(self, user_id: str, conversation_id: str) -> ConversationInDB | None:
        if not ObjectId.is_valid(conversation_id):
            return None
        doc = await self.collection.find_one(
            {"_id": ObjectId(conversation_id), "user_id": user_id}
        )
        return self._to_model(doc) if doc else None

    async def append_messages(
        self, user_id: str, conversation_id: str, messages: list[MessageSchema]
    ) -> ConversationInDB | None:
        if not ObjectId.is_valid(conversation_id):
            return None
        doc = await self.collection.find_one_and_update(
            {"_id": ObjectId(conversation_id), "user_id": user_id},
            {
                "$push": {"messages": {"$each": [m.model_dump(mode="python") for m in messages]}},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
            return_document=ReturnDocument.AFTER,
        )
        return self._to_model(doc) if doc else None

    async def list_for_agent(
        self,
        user_id: str,
        agent_id: str,
        company_id: str | None,
        limit: int,
        offset: int,
    ) -> list[ConversationInDB]:
        cursor = (
            self.collection.find({"user_id": user_id, "agent_id": agent_id, "company_id": company_id})
            .sort("updated_at", -1)
            .skip(offset)
            .limit(limit)
        )
        return [self._to_model(doc) async for doc in cursor]
