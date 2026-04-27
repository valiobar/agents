from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.user import UserInDB


class UserRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["users"]

    async def find_by_email(self, email: str) -> UserInDB | None:
        doc = await self.collection.find_one({"email": email})
        if not doc:
            return None
        doc["_id"] = str(doc["_id"])
        return UserInDB(**doc)

    async def find_by_google_id(self, google_id: str) -> UserInDB | None:
        doc = await self.collection.find_one({"google_id": google_id})
        if not doc:
            return None
        doc["_id"] = str(doc["_id"])
        return UserInDB(**doc)

    async def create(self, user_data: dict) -> UserInDB:
        user_data["created_at"] = datetime.now(timezone.utc)
        result = await self.collection.insert_one(user_data)
        user_data["_id"] = str(result.inserted_id)
        return UserInDB(**user_data)

    async def find_by_id(self, user_id: str) -> UserInDB | None:
        doc = await self.collection.find_one({"_id": ObjectId(user_id)})
        if not doc:
            return None
        doc["_id"] = str(doc["_id"])
        return UserInDB(**doc)

    async def update_auth_provider(
        self, user_id: str, provider: str, google_id: str | None = None
    ) -> None:
        update: dict = {"$set": {"auth_provider": provider}}
        if google_id:
            update["$set"]["google_id"] = google_id
        await self.collection.update_one({"_id": ObjectId(user_id)}, update)

