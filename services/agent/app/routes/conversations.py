from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_conversation_service, get_user_id
from app.models.conversation import ConversationResponse
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
    agent_id: str,
    company_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    conversations = await service.list_conversations(
        user_id=user_id,
        agent_id=agent_id,
        company_id=company_id,
        limit=limit,
        offset=offset,
    )
    return [ConversationResponse.model_validate(conversation) for conversation in conversations]


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[ConversationService, Depends(get_conversation_service)],
):
    conversation = await service.get_conversation(user_id, conversation_id)
    return ConversationResponse.model_validate(conversation)
