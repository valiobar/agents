from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
import json
import logging

from app.config import settings
from app.models.chat import ChatRequest
from app.models.conversation import MessageSchema
from app.models.usage import UsageEventCreate
from app.repositories.agent_repo import AgentRepository
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.usage_repo import UsageRepository
from app.runtime.providers.factory import LLMProviderFactory
from app.runtime.registry import create_agent_runtime
from app.runtime.tool_context import ToolContext

logger = logging.getLogger(__name__)


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class ChatService:
    def __init__(
        self,
        agent_repo: AgentRepository,
        conversation_repo: ConversationRepository,
        usage_repo: UsageRepository,
        tool_context: ToolContext,
    ) -> None:
        self.agent_repo = agent_repo
        self.conversation_repo = conversation_repo
        self.usage_repo = usage_repo
        self.tool_context = tool_context

    async def stream_chat(
        self,
        user_id: str,
        agent_id: str,
        payload: ChatRequest,
    ) -> AsyncIterator[str]:
        agent = await self.agent_repo.get_by_id(user_id, agent_id)
        if agent is None:
            yield sse("error", {"message": "Agent not found"})
            return

        try:
            provider = LLMProviderFactory.create(agent.config.provider)
            llm = provider.create_chat_model(agent.config.model, agent.config.temperature)
            runtime = create_agent_runtime(agent, llm, user_id, self.tool_context)
        except Exception as exc:
            yield sse("error", {"message": str(exc)})
            return

        if payload.conversation_id:
            conversation = await self.conversation_repo.get_by_id(user_id, payload.conversation_id)
            if (
                conversation is None
                or conversation.agent_id != agent.id
                or conversation.company_id != agent.company_id
            ):
                yield sse("error", {"message": "Conversation not found"})
                return
        else:
            conversation = await self.conversation_repo.create(
                user_id=user_id,
                agent_id=agent.id,
                company_id=agent.company_id,
                first_message=payload.message,
            )
            yield sse("conversation", {"conversation_id": conversation.id})

        history = conversation.messages[-settings.max_history_messages :]

        assistant_parts: list[str] = []
        runtime_usage_events = []
        yield sse("start", {"conversation_id": conversation.id})

        try:
            async for token in runtime.run(payload.message, history):
                assistant_parts.append(token)
                yield sse("token", {"content": token})
            runtime_usage_events = runtime.consume_usage_events()
        except Exception as exc:
            yield sse("error", {"message": str(exc)})
            return

        now = datetime.now(timezone.utc)
        saved = await self.conversation_repo.append_messages(
            user_id=user_id,
            conversation_id=conversation.id,
            messages=[
                MessageSchema(role="user", content=payload.message, created_at=now),
                MessageSchema(
                    role="assistant",
                    content="".join(assistant_parts),
                    created_at=now,
                ),
            ],
        )
        if saved is None:
            logger.error(
                "failed_to_persist_chat_messages",
                extra={
                    "user_id": user_id,
                    "agent_id": agent.id,
                    "conversation_id": conversation.id,
                },
            )
            yield sse("error", {"message": "Failed to persist conversation messages"})
            return

        usage_events = [
            UsageEventCreate.from_runtime_event(
                event,
                conversation_id=conversation.id,
                created_at=now,
            )
            for event in runtime_usage_events
            if event.input_tokens is not None
            or event.output_tokens is not None
            or event.total_tokens is not None
        ]
        try:
            await self.usage_repo.insert_many(usage_events)
        except Exception:
            logger.exception(
                "failed_to_persist_usage_events",
                extra={
                    "user_id": user_id,
                    "agent_id": agent.id,
                    "conversation_id": conversation.id,
                },
            )

        yield sse("done", {"conversation_id": conversation.id})
