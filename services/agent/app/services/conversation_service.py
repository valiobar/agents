from __future__ import annotations

from fastapi import HTTPException, status

from app.models.shared.conversation import ConversationInDB
from app.repositories.conversation_repo import ConversationRepository


class ConversationService:
    def __init__(self, repo: ConversationRepository) -> None:
        self.repo = repo

    async def get_conversation(self, user_id: str, conversation_id: str) -> ConversationInDB:
        conversation = await self.repo.get_by_id(user_id, conversation_id)
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        return conversation

    async def list_conversations(
        self,
        user_id: str,
        agent_id: str,
        company_id: str | None,
        limit: int,
        offset: int,
    ) -> list[ConversationInDB]:
        return await self.repo.list_for_agent(
            user_id=user_id,
            agent_id=agent_id,
            company_id=company_id,
            limit=limit,
            offset=offset,
        )

