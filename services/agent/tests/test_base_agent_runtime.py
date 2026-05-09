from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from langchain_core.language_models.fake_chat_models import FakeListChatModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.shared.agent import AgentConfig, AgentInDB
from app.config import settings
from app.runtime.base_agent import BaseAgent
from app.runtime.hooks import AgentRunChunk, AgentRunEvent, AgentRunInput, AgentRunResult


def fake_agent() -> AgentInDB:
    now = datetime.now(UTC)
    return AgentInDB(
        id="agent-1",
        user_id="user-1",
        name="Runtime Test Agent",
        description=None,
        agent_type="accountant",
        company_id=None,
        config=AgentConfig(provider="openai", model="gpt-4.1-mini", temperature=0.2),
        created_at=now,
        updated_at=now,
    )


def fake_context() -> object:
    return SimpleNamespace(business_client=None, companybook_service=None, knowledge_http=None)


def stream_event(content: str, *, run_id: str = "run-1", usage: dict | None = None) -> dict:
    return {
        "event": "on_chat_model_stream",
        "name": "ChatOpenAI",
        "run_id": run_id,
        "data": {"chunk": SimpleNamespace(content=content, usage_metadata=usage or {})},
    }


def start_event(*, run_id: str = "run-1") -> dict:
    return {
        "event": "on_chat_model_start",
        "name": "ChatOpenAI",
        "run_id": run_id,
        "data": {},
    }


def end_event(*, run_id: str = "run-1", usage: dict | None = None) -> dict:
    return {
        "event": "on_chat_model_end",
        "name": "ChatOpenAI",
        "run_id": run_id,
        "data": {"output": SimpleNamespace(usage_metadata=usage or {})},
    }


def chain_end_event(output: str) -> dict:
    return {
        "event": "on_chain_end",
        "name": "AgentExecutor",
        "run_id": "chain-1",
        "data": {"output": {"output": output}},
    }


def tool_start_event(tool_name: str, input_payload: dict | None = None) -> dict:
    return {
        "event": "on_tool_start",
        "name": tool_name,
        "run_id": "tool-run-1",
        "data": {"input": input_payload or {}},
    }


def tool_end_event(tool_name: str, *, output_payload: dict | None = None, duration_ms: int | None = None) -> dict:
    data: dict[str, object] = {"output": output_payload or {}}
    if duration_ms is not None:
        data["duration_ms"] = duration_ms
    return {
        "event": "on_tool_end",
        "name": tool_name,
        "run_id": "tool-run-1",
        "data": data,
    }


class FakeExecutor:
    events: list[dict] = []
    last_payload: dict | None = None

    def __init__(self, *, agent, tools, max_iterations) -> None:
        self.agent = agent
        self.tools = tools
        self.max_iterations = max_iterations

    async def astream_events(self, payload: dict, version: str):
        FakeExecutor.last_payload = payload
        for event in FakeExecutor.events:
            yield event


class NoHookAgent(BaseAgent):
    def get_tools(self):
        return []

    def get_system_prompt(self) -> str:
        return "system"


class HookedAgent(NoHookAgent):
    async def prepare_run_input(self, run_input: AgentRunInput) -> AgentRunInput:
        run_input.message = f"prefix: {run_input.message}"
        run_input.metadata["prepared"] = True
        return run_input

    async def on_event(self, event: AgentRunEvent) -> AgentRunEvent:
        event.metadata["event_seen"] = True
        if event.event == "on_chat_model_stream":
            chunk = event.raw.get("data", {}).get("chunk")
            if chunk is not None:
                chunk.content = f"{chunk.content}-event"
        return event

    async def on_chunk(self, chunk: AgentRunChunk) -> AgentRunChunk:
        assert chunk.metadata["prepared"] is True
        assert chunk.metadata["event_seen"] is True
        chunk.text = chunk.text.upper()
        return chunk


class SuppressingAgent(NoHookAgent):
    async def on_chunk(self, chunk: AgentRunChunk) -> AgentRunChunk:
        chunk.text = ""
        return chunk


class ExplodingChunkAgent(NoHookAgent):
    async def on_chunk(self, chunk: AgentRunChunk) -> AgentRunChunk:
        raise RuntimeError("chunk hook failure")


class MetadataTrackingAgent(NoHookAgent):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.duplicate_hits = 0
        self.run_seen_sizes: list[int] = []

    async def on_event(self, event: AgentRunEvent) -> AgentRunEvent:
        if event.event == "on_tool_start":
            query = event.raw.get("data", {}).get("input", {}).get("query")
            if isinstance(query, str):
                seen = event.metadata.setdefault("queries", set())
                if query in seen:
                    self.duplicate_hits += 1
                else:
                    seen.add(query)
        return event

    async def on_run_end(self, result: AgentRunResult) -> AgentRunResult:
        self.run_seen_sizes.append(len(result.metadata.get("queries", set())))
        return result


class BaseAgentRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_hooks_are_noop(self) -> None:
        FakeExecutor.events = [stream_event("hello")]
        runtime = NoHookAgent(fake_agent(), FakeListChatModel(responses=["unused"]), "user-1", fake_context())
        with patch("app.runtime.base_agent.create_tool_calling_agent", return_value=object()), patch(
            "app.runtime.base_agent.AgentExecutor",
            FakeExecutor,
        ):
            tokens = [token async for token in runtime.run("hello", [])]

        self.assertEqual(tokens, ["hello"])
        assert FakeExecutor.last_payload is not None
        self.assertEqual(FakeExecutor.last_payload["input"], "hello")

    async def test_hooks_mutate_input_and_chunks(self) -> None:
        FakeExecutor.events = [stream_event("hello")]
        runtime = HookedAgent(fake_agent(), FakeListChatModel(responses=["unused"]), "user-1", fake_context())
        with patch("app.runtime.base_agent.create_tool_calling_agent", return_value=object()), patch(
            "app.runtime.base_agent.AgentExecutor",
            FakeExecutor,
        ):
            tokens = [token async for token in runtime.run("hello", [])]

        self.assertEqual(tokens, ["HELLO-EVENT"])
        assert FakeExecutor.last_payload is not None
        self.assertEqual(FakeExecutor.last_payload["input"], "prefix: hello")

    async def test_empty_transformed_chunks_are_suppressed_and_fallback_still_emits(self) -> None:
        FakeExecutor.events = [stream_event("hello"), chain_end_event("fallback output")]
        runtime = SuppressingAgent(fake_agent(), FakeListChatModel(responses=["unused"]), "user-1", fake_context())
        with patch("app.runtime.base_agent.create_tool_calling_agent", return_value=object()), patch(
            "app.runtime.base_agent.AgentExecutor",
            FakeExecutor,
        ):
            tokens = [token async for token in runtime.run("hello", [])]

        self.assertEqual(tokens, ["fallback output"])

    async def test_hook_errors_propagate_from_run(self) -> None:
        FakeExecutor.events = [stream_event("hello")]
        runtime = ExplodingChunkAgent(
            fake_agent(),
            FakeListChatModel(responses=["unused"]),
            "user-1",
            fake_context(),
        )
        with patch("app.runtime.base_agent.create_tool_calling_agent", return_value=object()), patch(
            "app.runtime.base_agent.AgentExecutor",
            FakeExecutor,
        ):
            with self.assertRaisesRegex(RuntimeError, "chunk hook failure"):
                _ = [token async for token in runtime.run("hello", [])]

    async def test_usage_events_are_collected_and_consumed_once(self) -> None:
        FakeExecutor.events = [
            start_event(),
            stream_event("hello", usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}),
            end_event(usage={"output_tokens": 7, "total_tokens": 17}),
        ]
        runtime = NoHookAgent(fake_agent(), FakeListChatModel(responses=["unused"]), "user-1", fake_context())
        with patch("app.runtime.base_agent.create_tool_calling_agent", return_value=object()), patch(
            "app.runtime.base_agent.AgentExecutor",
            FakeExecutor,
        ):
            tokens = [token async for token in runtime.run("hello", [])]

        self.assertEqual(tokens, ["hello"])
        usage = runtime.consume_usage_events()
        self.assertEqual(len(usage), 1)
        self.assertEqual(usage[0].input_tokens, 10)
        self.assertEqual(usage[0].output_tokens, 7)
        self.assertEqual(usage[0].total_tokens, 17)
        self.assertEqual(runtime.consume_usage_events(), [])

    async def test_run_metadata_is_scoped_per_run(self) -> None:
        runtime = MetadataTrackingAgent(
            fake_agent(),
            FakeListChatModel(responses=["unused"]),
            "user-1",
            fake_context(),
        )

        FakeExecutor.events = [
            tool_start_event("search_inventory_stock", {"query": "sku-1"}),
            tool_start_event("search_inventory_stock", {"query": "sku-1"}),
            chain_end_event("done"),
        ]
        with patch("app.runtime.base_agent.create_tool_calling_agent", return_value=object()), patch(
            "app.runtime.base_agent.AgentExecutor",
            FakeExecutor,
        ):
            _ = [token async for token in runtime.run("first", [])]

        FakeExecutor.events = [
            tool_start_event("search_inventory_stock", {"query": "sku-1"}),
            chain_end_event("done"),
        ]
        with patch("app.runtime.base_agent.create_tool_calling_agent", return_value=object()), patch(
            "app.runtime.base_agent.AgentExecutor",
            FakeExecutor,
        ):
            _ = [token async for token in runtime.run("second", [])]

        self.assertEqual(runtime.duplicate_hits, 1)
        self.assertEqual(runtime.run_seen_sizes, [1, 1])

    async def test_tool_trace_ui_events_emit_only_when_debug_flag_enabled(self) -> None:
        runtime = NoHookAgent(fake_agent(), FakeListChatModel(responses=["unused"]), "user-1", fake_context())
        FakeExecutor.events = [
            tool_start_event(
                "search_inventory_stock",
                {"query": "iphone", "token": "secret-token"},
            ),
            tool_end_event("search_inventory_stock", output_payload={"rows": 1}, duration_ms=42),
            chain_end_event("done"),
        ]

        with patch("app.runtime.base_agent.create_tool_calling_agent", return_value=object()), patch(
            "app.runtime.base_agent.AgentExecutor",
            FakeExecutor,
        ), patch.object(settings, "agent_environment", "development"), patch.object(
            settings,
            "agent_debug_tool_traces",
            True,
        ):
            _ = [token async for token in runtime.run("trace", [])]
            ui_events = runtime.consume_ui_events()

        tool_traces = [payload for event_name, payload in ui_events if event_name == "tool_trace"]
        self.assertEqual(len(tool_traces), 2)
        self.assertEqual(tool_traces[0]["tool_name"], "search_inventory_stock")
        self.assertEqual(tool_traces[0]["phase"], "on_tool_start")
        self.assertIn("REDACTED", tool_traces[0]["args_preview"])
        self.assertEqual(tool_traces[1]["duration_ms"], 42)


if __name__ == "__main__":
    unittest.main()
