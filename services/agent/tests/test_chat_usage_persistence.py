from __future__ import annotations

from asyncio import sleep
from datetime import UTC, datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.shared.agent import AgentConfig, AgentInDB
from app.models.shared.chat import ChatRequest
from app.models.shared.conversation import ConversationInDB
from app.runtime.usage import LLMUsageEvent
from app.services.chat_service import ChatService


def fake_agent() -> AgentInDB:
    now = datetime.now(UTC)
    return AgentInDB(
        id="agent-1",
        user_id="user-1",
        name="Chat Usage Agent",
        description=None,
        agent_type="accountant",
        company_id=None,
        config=AgentConfig(provider="openai", model="gpt-4.1-mini", temperature=0.2),
        created_at=now,
        updated_at=now,
    )


def fake_usage_event() -> LLMUsageEvent:
    now = datetime.now(UTC)
    return LLMUsageEvent(
        user_id="user-1",
        agent_id="agent-1",
        provider="openai",
        model="gpt-4.1-mini",
        run_id="run-1",
        llm_call_index=1,
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        stream_chunks=1,
        stream_chars=5,
        started_at=now,
        completed_at=now,
        duration_ms=100,
    )


class FakeProvider:
    def create_chat_model(self, model: str | None, temperature: float):
        return object()


class FakeAgentRepo:
    async def get_by_id(self, user_id: str, agent_id: str):
        await sleep(0)
        return fake_agent()


class FakeConversationRepo:
    def __init__(self, *, append_succeeds: bool = True) -> None:
        self.append_succeeds = append_succeeds
        self.created_ids: list[str] = []
        self.appended_calls = 0

    async def get_by_id(self, user_id: str, conversation_id: str):
        await sleep(0)
        return None

    async def create(self, user_id: str, agent_id: str, company_id: str | None, first_message: str) -> ConversationInDB:
        await sleep(0)
        now = datetime.now(UTC)
        self.created_ids.append("conversation-1")
        return ConversationInDB(
            id="conversation-1",
            user_id=user_id,
            agent_id=agent_id,
            company_id=company_id,
            title=first_message,
            messages=[],
            created_at=now,
            updated_at=now,
        )

    async def append_messages(self, user_id: str, conversation_id: str, messages):
        await sleep(0)
        self.appended_calls += 1
        if self.append_succeeds:
            return object()
        return None


class FakeUsageRepo:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.events = []
        self.calls = 0

    async def insert_many(self, events):
        await sleep(0)
        self.calls += 1
        if self.fail:
            raise RuntimeError("usage write failed")
        self.events.extend(events)
        return len(events)


class FakeRuntime:
    async def run(self, message, history):
        yield "hello"

    def consume_usage_events(self):
        return [fake_usage_event()]


class FakeDelegatedRuntime(FakeRuntime):
    def consume_usage_events(self):
        event = fake_usage_event()
        return [
            LLMUsageEvent(
                user_id=event.user_id,
                agent_id="delegate-inventory-1",
                provider=event.provider,
                model=event.model,
                run_id=event.run_id,
                llm_call_index=event.llm_call_index,
                input_tokens=event.input_tokens,
                output_tokens=event.output_tokens,
                total_tokens=event.total_tokens,
                stream_chunks=event.stream_chunks,
                stream_chars=event.stream_chars,
                started_at=event.started_at,
                completed_at=event.completed_at,
                duration_ms=event.duration_ms,
                source=event.source,
            )
        ]


class ChatUsagePersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_persists_usage_after_messages(self) -> None:
        conversation_repo = FakeConversationRepo(append_succeeds=True)
        usage_repo = FakeUsageRepo()
        service = ChatService(FakeAgentRepo(), conversation_repo, usage_repo, object())

        with patch("app.services.chat_service.LLMProviderFactory.create", return_value=FakeProvider()), patch(
            "app.services.chat_service.create_agent_runtime",
            return_value=FakeRuntime(),
        ):
            events = [chunk async for chunk in service.stream_chat("user-1", "agent-1", ChatRequest(message="hi"))]

        self.assertTrue(events[0].startswith("event: conversation"))
        self.assertTrue(events[1].startswith("event: start"))
        self.assertTrue(events[2].startswith("event: token"))
        self.assertTrue(events[3].startswith("event: done"))
        self.assertEqual(conversation_repo.appended_calls, 1)
        self.assertEqual(usage_repo.calls, 1)
        self.assertEqual(len(usage_repo.events), 1)

    async def test_usage_persistence_failure_still_emits_done(self) -> None:
        conversation_repo = FakeConversationRepo(append_succeeds=True)
        usage_repo = FakeUsageRepo(fail=True)
        service = ChatService(FakeAgentRepo(), conversation_repo, usage_repo, object())

        with patch("app.services.chat_service.LLMProviderFactory.create", return_value=FakeProvider()), patch(
            "app.services.chat_service.create_agent_runtime",
            return_value=FakeRuntime(),
        ):
            events = [chunk async for chunk in service.stream_chat("user-1", "agent-1", ChatRequest(message="hi"))]

        self.assertTrue(any(item.startswith("event: done") for item in events))
        self.assertFalse(any(item.startswith("event: error") for item in events))
        self.assertEqual(conversation_repo.appended_calls, 1)
        self.assertEqual(usage_repo.calls, 1)

    async def test_message_persistence_failure_prevents_usage_persistence(self) -> None:
        conversation_repo = FakeConversationRepo(append_succeeds=False)
        usage_repo = FakeUsageRepo()
        service = ChatService(FakeAgentRepo(), conversation_repo, usage_repo, object())

        with patch("app.services.chat_service.LLMProviderFactory.create", return_value=FakeProvider()), patch(
            "app.services.chat_service.create_agent_runtime",
            return_value=FakeRuntime(),
        ):
            events = [chunk async for chunk in service.stream_chat("user-1", "agent-1", ChatRequest(message="hi"))]

        self.assertTrue(any(item.startswith("event: error") for item in events))
        self.assertFalse(any(item.startswith("event: done") for item in events))
        self.assertEqual(conversation_repo.appended_calls, 1)
        self.assertEqual(usage_repo.calls, 0)
        self.assertEqual(usage_repo.events, [])

    async def test_persists_usage_from_delegated_runtime_agent_id(self) -> None:
        conversation_repo = FakeConversationRepo(append_succeeds=True)
        usage_repo = FakeUsageRepo()
        service = ChatService(FakeAgentRepo(), conversation_repo, usage_repo, object())

        with patch("app.services.chat_service.LLMProviderFactory.create", return_value=FakeProvider()), patch(
            "app.services.chat_service.create_agent_runtime",
            return_value=FakeDelegatedRuntime(),
        ):
            _ = [chunk async for chunk in service.stream_chat("user-1", "agent-1", ChatRequest(message="hi"))]

        self.assertEqual(usage_repo.calls, 1)
        self.assertEqual(len(usage_repo.events), 1)
        self.assertEqual(usage_repo.events[0].agent_id, "delegate-inventory-1")


if __name__ == "__main__":
    unittest.main()
