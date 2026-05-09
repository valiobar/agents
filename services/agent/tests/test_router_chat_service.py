from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, Mock, call, patch

from langchain_core.language_models.fake_chat_models import FakeListChatModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.shared.agent import AgentConfig, AgentInDB
from app.models.shared.chat import ChatRequest
from app.models.shared.conversation import ConversationInDB
from app.runtime.router import RouterAgent
from app.runtime.usage import LLMUsageEvent
from app.config import settings
from app.services.chat_service import ChatService


def fake_agent(
    *,
    agent_id: str,
    agent_type: str,
    company_id: str | None,
    parent_agent_id: str | None = None,
    delegate_role: str | None = None,
) -> AgentInDB:
    now = datetime.now(UTC)
    data = {
        "id": agent_id,
        "user_id": "user-1",
        "name": f"{agent_type}-{agent_id}",
        "description": None,
        "agent_type": agent_type,
        "company_id": company_id,
        "config": AgentConfig(provider="openai", model="gpt-4.1-mini", temperature=0.2),
        "created_at": now,
        "updated_at": now,
    }
    if parent_agent_id is not None:
        data["parent_agent_id"] = parent_agent_id
    if delegate_role is not None:
        data["delegate_role"] = delegate_role
    return AgentInDB.model_validate(data)


def fake_conversation(agent_id: str, *, company_id: str | None) -> ConversationInDB:
    now = datetime.now(UTC)
    return ConversationInDB(
        id="conversation-1",
        user_id="user-1",
        agent_id=agent_id,
        company_id=company_id,
        title="title",
        messages=[],
        created_at=now,
        updated_at=now,
    )


def fake_usage_event(*, agent_id: str) -> LLMUsageEvent:
    now = datetime.now(UTC)
    return LLMUsageEvent(
        user_id="user-1",
        agent_id=agent_id,
        provider="openai",
        model="gpt-4.1-mini",
        run_id="run-1",
        llm_call_index=1,
        input_tokens=3,
        output_tokens=2,
        total_tokens=5,
        stream_chunks=1,
        stream_chars=4,
        started_at=now,
        completed_at=now,
        duration_ms=10,
    )


class FakeProvider:
    def create_chat_model(self, model: str | None, temperature: float):
        return FakeListChatModel(responses=["unused"])


class FakeRuntime:
    def __init__(
        self,
        *,
        token: str = "ok",
        route_metadata: dict | None = None,
        ui_events: list[tuple[str, dict]] | None = None,
    ) -> None:
        self.token = token
        self.route_metadata = route_metadata
        self._usage_events: list[LLMUsageEvent] = []
        self._ui_events = ui_events or []

    async def run(self, message, history):
        yield self.token

    def consume_usage_events(self):
        events = self._usage_events
        self._usage_events = []
        return events

    def consume_ui_events(self):
        events = self._ui_events
        self._ui_events = []
        return events


class RouterChatServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_runtime_configures_router_children(self) -> None:
        router_agent = fake_agent(agent_id="router-1", agent_type="router", company_id="company-1")
        accountant_agent = fake_agent(
            agent_id="acct-1",
            agent_type="accountant",
            company_id="company-1",
            parent_agent_id="router-1",
            delegate_role="accountant",
        )
        inventory_agent = fake_agent(
            agent_id="inv-1",
            agent_type="inventory",
            company_id="company-1",
            parent_agent_id="router-1",
            delegate_role="inventory",
        )
        agent_repo = AsyncMock()
        agent_repo.get_delegate_for_router = AsyncMock(side_effect=[accountant_agent, inventory_agent])
        agent_repo.get_latest_by_type = AsyncMock()
        service = ChatService(agent_repo, AsyncMock(), AsyncMock(), object())

        router_runtime = RouterAgent(router_agent, FakeListChatModel(responses=["unused"]), "user-1", object())
        accountant_runtime = FakeRuntime(token="acct")
        inventory_runtime = FakeRuntime(token="inv")

        with patch("app.services.chat_service.LLMProviderFactory.create", return_value=FakeProvider()), patch(
            "app.services.chat_service.create_agent_runtime",
            side_effect=[router_runtime, accountant_runtime, inventory_runtime],
        ):
            runtime = await service._create_runtime("user-1", router_agent)

        self.assertIs(runtime, router_runtime)
        self.assertIs(router_runtime.accountant_runtime, accountant_runtime)
        self.assertIs(router_runtime.inventory_runtime, inventory_runtime)
        self.assertEqual(
            agent_repo.get_delegate_for_router.await_args_list,
            [call("user-1", "router-1", "accountant"), call("user-1", "router-1", "inventory")],
        )
        agent_repo.get_latest_by_type.assert_not_awaited()

    async def test_unassigned_router_uses_unassigned_child_fallback_lookup(self) -> None:
        router_agent = fake_agent(agent_id="router-1", agent_type="router", company_id=None)
        accountant_agent = fake_agent(agent_id="acct-u", agent_type="accountant", company_id=None)

        agent_repo = AsyncMock()
        agent_repo.get_delegate_for_router = AsyncMock(side_effect=[None, None])
        agent_repo.get_latest_by_type = AsyncMock(side_effect=[accountant_agent, None])
        service = ChatService(agent_repo, AsyncMock(), AsyncMock(), object())

        router_runtime = RouterAgent(router_agent, FakeListChatModel(responses=["unused"]), "user-1", object())
        accountant_runtime = FakeRuntime(token="acct")

        with patch("app.services.chat_service.LLMProviderFactory.create", return_value=FakeProvider()), patch(
            "app.services.chat_service.create_agent_runtime",
            side_effect=[router_runtime, accountant_runtime],
        ):
            runtime = await service._create_runtime("user-1", router_agent)

        self.assertIs(runtime, router_runtime)
        self.assertIsNotNone(router_runtime.accountant_runtime)
        self.assertIsNone(router_runtime.inventory_runtime)
        self.assertEqual(
            agent_repo.get_latest_by_type.await_args_list,
            [call("user-1", "accountant", None), call("user-1", "inventory", None)],
        )

    async def test_stream_chat_emits_route_before_done(self) -> None:
        router_agent = fake_agent(agent_id="router-1", agent_type="router", company_id="company-1")
        runtime = FakeRuntime(
            token="Hello",
            route_metadata={
                "predicted_route": "inventory",
                "executed_route": "inventory",
                "reason": "stock",
                "confidence": 0.95,
                "company_id": "company-1",
                "company_scope": "assigned",
            },
        )
        runtime._usage_events = [fake_usage_event(agent_id="delegate-inv-1")]

        agent_repo = AsyncMock()
        agent_repo.get_by_id = AsyncMock(return_value=router_agent)
        conversation_repo = AsyncMock()
        conversation_repo.create = AsyncMock(return_value=fake_conversation("router-1", company_id="company-1"))
        conversation_repo.append_messages = AsyncMock(return_value=object())
        usage_repo = AsyncMock()
        usage_repo.insert_many = AsyncMock(return_value=1)
        service = ChatService(agent_repo, conversation_repo, usage_repo, object())

        with patch.object(service, "_create_runtime", new=AsyncMock(return_value=runtime)):
            events = [chunk async for chunk in service.stream_chat("user-1", "router-1", ChatRequest(message="stock?"))]

        route_idx = next(i for i, item in enumerate(events) if item.startswith("event: route"))
        done_idx = next(i for i, item in enumerate(events) if item.startswith("event: done"))
        self.assertLess(route_idx, done_idx)

        persisted_events = usage_repo.insert_many.await_args.args[0]
        self.assertEqual(len(persisted_events), 1)
        self.assertEqual(persisted_events[0].agent_id, "delegate-inv-1")

    async def test_stream_chat_skips_tool_trace_when_setting_disabled(self) -> None:
        router_agent = fake_agent(agent_id="router-1", agent_type="router", company_id="company-1")
        runtime = FakeRuntime(
            token="Hello",
            ui_events=[
                (
                    "tool_trace",
                    {
                        "tool_name": "search_inventory_stock",
                        "phase": "on_tool_end",
                        "args_preview": "{\"query\":\"iphone\"}",
                        "duration_ms": 11,
                        "status": "ok",
                        "output_bytes": 12,
                    },
                )
            ],
        )

        agent_repo = AsyncMock()
        agent_repo.get_by_id = AsyncMock(return_value=router_agent)
        conversation_repo = AsyncMock()
        conversation_repo.create = AsyncMock(return_value=fake_conversation("router-1", company_id="company-1"))
        conversation_repo.append_messages = AsyncMock(return_value=object())
        usage_repo = AsyncMock()
        usage_repo.insert_many = AsyncMock(return_value=1)
        service = ChatService(agent_repo, conversation_repo, usage_repo, object())

        with patch.object(service, "_create_runtime", new=AsyncMock(return_value=runtime)), patch.object(
            settings,
            "agent_debug_tool_traces",
            False,
        ):
            events = [chunk async for chunk in service.stream_chat("user-1", "router-1", ChatRequest(message="stock?"))]

        self.assertFalse(any(event.startswith("event: tool_trace") for event in events))


if __name__ == "__main__":
    unittest.main()
