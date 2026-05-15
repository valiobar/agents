from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timezone
import json
import logging
from typing import Literal

from app.config import settings
from app.models.shared.agent import AgentInDB
from app.models.shared.chat import ChatRequest
from app.models.shared.conversation import MessageSchema
from app.models.shared.usage import UsageEventCreate
from app.repositories.agent_repo import AgentRepository
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.usage_repo import UsageRepository
from app.runtime.base_agent import BaseAgent
from app.runtime.providers.factory import LLMProviderFactory
from app.runtime.registry import create_agent_runtime
from app.runtime.router import RouterAgent
from app.runtime.tool_context import ToolContext
from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)

DelegateRole = Literal["accountant", "inventory"]


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

    def _create_llm(self, agent: AgentInDB) -> BaseChatModel:
        provider = LLMProviderFactory.create(agent.config.provider)
        return provider.create_chat_model(agent.config.model, agent.config.temperature)

    async def _create_runtime(self, user_id: str, agent: AgentInDB) -> BaseAgent:
        llm = self._create_llm(agent)
        runtime = create_agent_runtime(agent, llm, user_id, self.tool_context)

        if isinstance(runtime, RouterAgent):
            accountant = await self._create_router_child_runtime(user_id, agent, "accountant")
            inventory = await self._create_router_child_runtime(user_id, agent, "inventory")
            runtime.configure_children(
                accountant_runtime=accountant,
                inventory_runtime=inventory,
                fallback_llm=llm,
            )
        return runtime

    async def _create_router_child_runtime(
        self,
        user_id: str,
        router: AgentInDB,
        delegate_role: DelegateRole,
    ) -> BaseAgent | None:
        child = await self.agent_repo.get_delegate_for_router(user_id, router.id, delegate_role)
        if child is None:
            # Backward-compatible fallback for routers created before delegate linking existed.
            child = await self.agent_repo.get_latest_by_type(user_id, delegate_role, router.company_id)

        if child is None:
            return None

        if child.company_id != router.company_id:
            logger.warning(
                "router_delegate_company_mismatch",
                extra={
                    "router_id": router.id,
                    "child_id": child.id,
                    "child_agent_type": child.agent_type,
                    "child_company_id": child.company_id,
                    "router_company_id": router.company_id,
                    "user_id": user_id,
                },
            )
            return None

        llm = self._create_llm(child)
        return create_agent_runtime(child, llm, user_id, self.tool_context)

    def _route_metadata_payload(self, runtime: BaseAgent) -> dict | None:
        route_metadata = getattr(runtime, "route_metadata", None)
        if route_metadata is None:
            return None
        if hasattr(route_metadata, "model_dump"):
            return route_metadata.model_dump()
        if isinstance(route_metadata, dict):
            return route_metadata
        return None

    def _workflow_suggestion_payload(self, runtime: BaseAgent) -> dict | None:
        suggestion = runtime.workflow_suggestion
        if suggestion is None:
            return None
        if isinstance(suggestion, dict):
            return suggestion
        return None

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
            runtime = await self._create_runtime(user_id, agent)
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

        route_payload = self._route_metadata_payload(runtime)
        if route_payload is not None:
            yield sse("route", route_payload)

        workflow_suggestion_payload = self._workflow_suggestion_payload(runtime)
        if workflow_suggestion_payload is not None:
            yield sse("workflow_suggestion", workflow_suggestion_payload)

        for ui_event_name, ui_payload in runtime.consume_ui_events():
            if ui_event_name == "tool_trace" and not settings.should_emit_tool_traces:
                continue
            yield sse(ui_event_name, ui_payload)

        yield sse("done", {"conversation_id": conversation.id})
