from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
import logging
from typing import Any

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool

from app.config import settings
from app.models.agent import AgentInDB
from app.models.conversation import MessageSchema
from app.runtime.tool_context import ToolContext

_MAX_TOOL_LOG_CHARS = 500

logger = logging.getLogger(__name__)


def _stringify_chunk_content(content: str | list[str | dict] | None) -> str:
    if not content:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content)


def _event_data(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data", {})
    return data if isinstance(data, dict) else {}


def _stream_text_from_event(event: dict[str, Any]) -> str:
    if event.get("event") != "on_chat_model_stream":
        return ""
    chunk: Any = _event_data(event).get("chunk")
    return _stringify_chunk_content(getattr(chunk, "content", None))


def _final_output_from_event(event: dict[str, Any]) -> str:
    if event.get("event") != "on_chain_end" or event.get("name") != "AgentExecutor":
        return ""
    output = _event_data(event).get("output", {})
    if not isinstance(output, dict):
        return ""
    return str(output.get("output") or "")


def _preview_log_value(value: Any) -> str:
    if value is None:
        return ""
    text = value if isinstance(value, str) else repr(value)
    if len(text) <= _MAX_TOOL_LOG_CHARS:
        return text
    return f"{text[:_MAX_TOOL_LOG_CHARS]}..."


def _tool_log_extra(event: dict[str, Any], agent: AgentInDB, user_id: str) -> dict[str, Any]:
    return {
        "agent_id": agent.id,
        "agent_type": agent.agent_type,
        "user_id": user_id,
        "run_id": event.get("run_id"),
        "tool_name": event.get("name"),
    }


def _log_tool_event(event: dict[str, Any], agent: AgentInDB, user_id: str) -> None:
    if not settings.is_development:
        return

    event_name = event.get("event")
    if event_name not in {"on_tool_start", "on_tool_end", "on_tool_error"}:
        return

    data = _event_data(event)
    extra = _tool_log_extra(event, agent, user_id)
    tool_name = extra["tool_name"]
    run_id = extra["run_id"]
    context_line = f"agent={agent.agent_type}/{agent.id} user={user_id} run={run_id}"

    if event_name == "on_tool_start":
        tool_input = _preview_log_value(data.get("input"))
        logger.info(
            "[tool.start] %s\n    %s\n    input:  %s",
            tool_name,
            context_line,
            tool_input,
            extra={**extra, "tool_input": tool_input},
        )
        return

    if event_name == "on_tool_end":
        tool_output = _preview_log_value(data.get("output"))
        logger.info(
            "[tool.end  ] %s\n    %s\n    output: %s",
            tool_name,
            context_line,
            tool_output,
            extra={**extra, "tool_output": tool_output},
        )
        return

    tool_error = _preview_log_value(data.get("error"))
    logger.warning(
        "[tool.error] %s\n    %s\n    error:  %s",
        tool_name,
        context_line,
        tool_error,
        extra={**extra, "tool_error": tool_error},
    )


class BaseAgent(ABC):
    """Strategy contract for agent runtimes (no FastAPI or MongoDB imports)."""

    def __init__(self, agent: AgentInDB, llm: BaseChatModel, user_id: str, tool_context: ToolContext) -> None:
        self.agent = agent
        self.llm = llm
        self.user_id = user_id
        self.tool_context = tool_context

    @abstractmethod
    def get_tools(self) -> list[BaseTool]:
        raise NotImplementedError

    @abstractmethod
    def get_system_prompt(self) -> str:
        raise NotImplementedError

    def _to_chat_history(self, history: list[MessageSchema]) -> list[BaseMessage]:
        messages: list[BaseMessage] = []
        for item in history:
            if item.role == "user":
                messages.append(HumanMessage(content=item.content))
            elif item.role == "assistant":
                messages.append(AIMessage(content=item.content))
            elif item.role == "system":
                messages.append(SystemMessage(content=item.content))
        return messages

    async def _llm_heartbeat(self, state: dict[str, Any], interval_s: float = 10.0) -> None:
        """Emit periodic 'still waiting' logs while an LLM call is in flight.

        Without this a slow chat completion is indistinguishable from a hung
        one — you only see ``[llm.start]`` and then silence for 60+ seconds.
        """
        call_num = state.get("count", 0)
        started_at = state.get("started_at") or time.monotonic()
        while True:
            await asyncio.sleep(interval_s)
            elapsed = time.monotonic() - started_at
            first_token_at = state.get("first_token_at")
            chunks = state.get("stream_chunks", 0)
            chars = state.get("stream_chars", 0)
            phase = "waiting_first_token" if first_token_at is None else "streaming_response"
            logger.info(
                "[llm.wait  ] call #%d  elapsed=%.1fs phase=%s chunks=%d chars=%d\n    agent=%s/%s user=%s",
                call_num,
                elapsed,
                phase,
                chunks,
                chars,
                self.agent.agent_type,
                self.agent.id,
                self.user_id,
            )

    def _cancel_llm_heartbeat(self, state: dict[str, Any]) -> None:
        task = state.get("heartbeat")
        if task is not None and not task.done():
            task.cancel()
        state["heartbeat"] = None

    def _track_llm_event(
        self,
        event: dict[str, Any],
        state: dict[str, Any],
    ) -> None:
        """Record LLM call boundaries so stalled chat completions are visible.

        Mutates ``state`` (which the caller threads through the event loop):
        ``state["count"]`` for the running LLM call number,
        ``state["started_at"]`` for the in-progress call's monotonic start, and
        ``state["heartbeat"]`` for the asyncio task emitting periodic
        "still waiting" logs. Without these, a stalled chat call between
        tool steps would be indistinguishable from a complete hang.
        """
        event_name = event.get("event")
        if event_name == "on_chat_model_start":
            state["count"] = state.get("count", 0) + 1
            state["started_at"] = time.monotonic()
            state["first_token_at"] = None
            state["stream_chunks"] = 0
            state["stream_chars"] = 0
            if settings.is_development:
                model_name = getattr(self.llm, "model_name", None) or getattr(self.llm, "model", "unknown")
                logger.info(
                    "[llm.start ] call #%d model=%s timeout=%.0fs retries=%d\n    agent=%s/%s user=%s",
                    state["count"],
                    model_name,
                    settings.openai_chat_timeout_seconds,
                    settings.openai_chat_max_retries,
                    self.agent.agent_type,
                    self.agent.id,
                    self.user_id,
                )
                self._cancel_llm_heartbeat(state)
                state["heartbeat"] = asyncio.create_task(self._llm_heartbeat(state))
            return

        if event_name == "on_chat_model_stream":
            text = _stream_text_from_event(event)
            if not text or state.get("started_at") is None:
                return
            state["stream_chunks"] = state.get("stream_chunks", 0) + 1
            state["stream_chars"] = state.get("stream_chars", 0) + len(text)
            if not settings.is_development:
                return
            if state.get("first_token_at") is None:
                state["first_token_at"] = time.monotonic()
                ttft = state["first_token_at"] - state["started_at"]
                logger.info(
                    "[llm.first ] call #%d ttft=%.2fs first_chunk_chars=%d\n    agent=%s/%s user=%s",
                    state.get("count", 0),
                    ttft,
                    len(text),
                    self.agent.agent_type,
                    self.agent.id,
                    self.user_id,
                )
                return
            if state["stream_chunks"] % 25 == 0:
                elapsed = time.monotonic() - state["started_at"]
                logger.info(
                    "[llm.stream] call #%d elapsed=%.2fs chunks=%d chars=%d\n    agent=%s/%s user=%s",
                    state.get("count", 0),
                    elapsed,
                    state["stream_chunks"],
                    state["stream_chars"],
                    self.agent.agent_type,
                    self.agent.id,
                    self.user_id,
                )
            return

        if event_name == "on_chat_model_error":
            self._cancel_llm_heartbeat(state)
            error = _preview_log_value(_event_data(event).get("error"))
            logger.warning(
                "[llm.error ] call #%d\n    agent=%s/%s user=%s\n    error:  %s",
                state.get("count", 0),
                self.agent.agent_type,
                self.agent.id,
                self.user_id,
                error,
            )
            state["started_at"] = None
            return

        if event_name == "on_chat_model_end" and state.get("started_at") is not None:
            self._cancel_llm_heartbeat(state)
            elapsed = time.monotonic() - state["started_at"]
            ttft = None
            if state.get("first_token_at") is not None:
                ttft = state["first_token_at"] - state["started_at"]
            if settings.is_development or elapsed > 30.0:
                is_slow = elapsed > 30.0
                log_fn = logger.warning if is_slow else logger.info
                tag = "[llm.slow  ]" if is_slow else "[llm.end   ]"
                if ttft is None:
                    log_fn(
                        "%s call #%d  elapsed=%.2fs chunks=%d chars=%d ttft=n/a(no_stream_token)\n    agent=%s/%s user=%s",
                        tag,
                        state.get("count", 0),
                        elapsed,
                        state.get("stream_chunks", 0),
                        state.get("stream_chars", 0),
                        self.agent.agent_type,
                        self.agent.id,
                        self.user_id,
                    )
                else:
                    log_fn(
                        "%s call #%d  elapsed=%.2fs chunks=%d chars=%d ttft=%.2fs\n    agent=%s/%s user=%s",
                        tag,
                        state.get("count", 0),
                        elapsed,
                        state.get("stream_chunks", 0),
                        state.get("stream_chars", 0),
                        ttft,
                        self.agent.agent_type,
                        self.agent.id,
                        self.user_id,
                    )
            state["started_at"] = None

    async def run(self, message: str, history: list[MessageSchema]) -> AsyncIterator[str]:
        tools = self.get_tools()
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.get_system_prompt()),
                MessagesPlaceholder("chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )
        agent = create_tool_calling_agent(self.llm, tools, prompt)
        executor = AgentExecutor(
            agent=agent,
            tools=tools,
            max_iterations=settings.max_agent_iterations,
        )

        emitted_text = False
        final_output = ""
        llm_state: dict[str, Any] = {"count": 0, "started_at": None, "heartbeat": None}

        try:
            async for event in executor.astream_events(
                {
                    "input": message,
                    "chat_history": self._to_chat_history(history),
                },
                version="v2",
            ):
                self._track_llm_event(event, llm_state)
                _log_tool_event(event, self.agent, self.user_id)

                text = _stream_text_from_event(event)
                if text:
                    emitted_text = True
                    yield text
                    continue

                final_output = _final_output_from_event(event) or final_output
        finally:
            self._cancel_llm_heartbeat(llm_state)

        if not emitted_text and final_output:
            yield final_output
