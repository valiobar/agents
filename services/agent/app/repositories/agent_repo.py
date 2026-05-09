from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.models.shared.agent import AgentCreate, AgentInDB, AgentType, AgentUpdate


class AgentRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.collection = db["agents"]

    def _to_model(self, doc: dict) -> AgentInDB:
        return AgentInDB(
            id=str(doc["_id"]),
            user_id=doc["user_id"],
            name=doc["name"],
            description=doc.get("description"),
            agent_type=doc["agent_type"],
            company_id=doc.get("company_id"),
            config=doc["config"],
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )

    async def create(self, user_id: str, payload: AgentCreate) -> AgentInDB:
        now = datetime.now(timezone.utc)
        doc = payload.model_dump()
        doc.update({"user_id": user_id, "created_at": now, "updated_at": now})
        result = await self.collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return self._to_model(doc)

    async def list_by_user(
        self,
        user_id: str,
        limit: int,
        offset: int,
        *,
        company_id: str | None = None,
    ) -> list[AgentInDB]:
        query: dict = {"user_id": user_id}
        if company_id is not None:
            query["company_id"] = company_id
        cursor = (
            self.collection.find(query)
            .sort("created_at", -1)
            .skip(offset)
            .limit(limit)
        )
        return [self._to_model(doc) async for doc in cursor]

    async def get_by_id(self, user_id: str, agent_id: str) -> AgentInDB | None:
        if not ObjectId.is_valid(agent_id):
            return None
        doc = await self.collection.find_one({"_id": ObjectId(agent_id), "user_id": user_id})
        return self._to_model(doc) if doc else None

    async def update(self, user_id: str, agent_id: str, payload: AgentUpdate) -> AgentInDB | None:
        if not ObjectId.is_valid(agent_id):
            return None
        update = payload.model_dump(exclude_unset=True)
        if not update:
            return await self.get_by_id(user_id, agent_id)

        update["updated_at"] = datetime.now(timezone.utc)
        doc = await self.collection.find_one_and_update(
            {"_id": ObjectId(agent_id), "user_id": user_id},
            {"$set": update},
            return_document=ReturnDocument.AFTER,
        )
        return self._to_model(doc) if doc else None

    async def delete(self, user_id: str, agent_id: str) -> bool:
        if not ObjectId.is_valid(agent_id):
            return False
        result = await self.collection.delete_one({"_id": ObjectId(agent_id), "user_id": user_id})
        return result.deleted_count == 1

    async def count_by_company(self, user_id: str, company_id: str) -> int:
        # `company_id` is introduced later in the plan; this query becomes effective once present.
        return int(await self.collection.count_documents({"user_id": user_id, "company_id": company_id}))

    async def get_latest_by_type(
        self,
        user_id: str,
        agent_type: AgentType,
        company_id: str | None,
    ) -> AgentInDB | None:
        query: dict[str, object] = {
            "user_id": user_id,
            "agent_type": agent_type,
            "company_id": company_id,
        }
        doc = await self.collection.find_one(query, sort=[("created_at", -1)])
        return self._to_model(doc) if doc else None

    async def get_delegate_for_router(
        self,
        user_id: str,
        parent_agent_id: str,
        delegate_role: Literal["accountant", "inventory"],
    ) -> AgentInDB | None:
        """Return a linked hidden delegate runtime for a router, if present."""
        doc = await self.collection.find_one(
            {
                "user_id": user_id,
                "parent_agent_id": parent_agent_id,
                "delegate_role": delegate_role,
            },
            sort=[("created_at", -1)],
        )
        return self._to_model(doc) if doc else None
