from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import time
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings
from app.models.agent import AgentInDB
from app.runtime.usage import LLMUsageEvent, TokenUsage, extract_token_usage

logger = logging.getLogger(__name__)

_MAX_LOG_CHARS = 500


def stringify_chunk_content(content: str | list[str | dict[str, Any]] | None) -> str:
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


def event_data(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data", {})
    return data if isinstance(data, dict) else {}


def preview_log_value(value: Any) -> str:
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = value
    else:
        text = repr(value)
    return text if len(text) <= _MAX_LOG_CHARS else f"{text[:_MAX_LOG_CHARS]}..."


@dataclass(slots=True)
class LLMTraceState:
    count: int = 0
    run_id: str | None = None
    started_at_monotonic: float | None = None
    started_at_wall: datetime | None = None
    first_token_at_monotonic: float | None = None
    stream_chunks: int = 0
    stream_chars: int = 0
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    heartbeat: asyncio.Task[None] | None = None


class AgentLoopLogger:
    def __init__(self, *, agent: AgentInDB, user_id: str, llm: BaseChatModel) -> None:
        self.agent = agent
        self.user_id = user_id
        self.llm = llm
        self.usage_events: list[LLMUsageEvent] = []

    @property
    def model_name(self) -> str:
        return str(getattr(self.llm, "model_name", None) or getattr(self.llm, "model", None) or "unknown")

    @property
    def provider_name(self) -> str:
        provider = getattr(self.llm, "_llm_type", None)
        return str(provider or self.agent.config.provider)

    def run_start(self, message: str, history_count: int, tool_names: list[str]) -> None:
        if settings.is_development:
            logger.info(
                "[agent.start] %s/%s user=%s history=%d tools=%s\n    input: %s",
                self.agent.agent_type,
                self.agent.id,
                self.user_id,
                history_count,
                tool_names,
                preview_log_value(message),
            )

    def executor_ready(self) -> None:
        if settings.is_development:
            logger.info(
                "[agent.ready ] %s/%s user=%s max_iterations=%d",
                self.agent.agent_type,
                self.agent.id,
                self.user_id,
                settings.max_agent_iterations,
            )

    def track_event(self, event: dict[str, Any], state: LLMTraceState) -> None:
        event_name = event.get("event")
        if event_name == "on_chat_model_start":
            self._start_llm_call(event, state)
        elif event_name == "on_chat_model_stream":
            self._track_stream_chunk(event, state)
        elif event_name == "on_chat_model_end":
            self._end_llm_call(event, state)
        elif event_name == "on_chat_model_error":
            self._error_llm_call(event, state)
        elif event_name in {"on_tool_start", "on_tool_end", "on_tool_error"}:
            self._log_tool_event(event)

    def _start_llm_call(self, event: dict[str, Any], state: LLMTraceState) -> None:
        state.count += 1
        state.run_id = event.get("run_id") if isinstance(event.get("run_id"), str) else None
        state.started_at_monotonic = time.monotonic()
        state.started_at_wall = datetime.now(timezone.utc)
        state.first_token_at_monotonic = None
        state.stream_chunks = 0
        state.stream_chars = 0
        state.token_usage = TokenUsage()
        self.cancel_heartbeat(state)
        if settings.is_development:
            logger.info(
                "[llm.start ] call #%d model=%s provider=%s timeout=%.0fs retries=%d\n"
                "    agent=%s/%s user=%s run=%s",
                state.count,
                self.model_name,
                self.provider_name,
                settings.openai_chat_timeout_seconds,
                settings.openai_chat_max_retries,
                self.agent.agent_type,
                self.agent.id,
                self.user_id,
                state.run_id,
            )
            state.heartbeat = asyncio.create_task(self.llm_heartbeat(state))

    def _track_stream_chunk(self, event: dict[str, Any], state: LLMTraceState) -> None:
        if state.started_at_monotonic is None:
            return
        chunk = event_data(event).get("chunk")
        text = stringify_chunk_content(getattr(chunk, "content", None))
        state.token_usage.merge(extract_token_usage(chunk))
        if not text:
            return

        state.stream_chunks += 1
        state.stream_chars += len(text)
        if not settings.is_development:
            return
        if state.first_token_at_monotonic is None:
            state.first_token_at_monotonic = time.monotonic()
            ttft = state.first_token_at_monotonic - state.started_at_monotonic
            logger.info(
                "[llm.first ] call #%d ttft=%.2fs first_chunk_chars=%d\n    agent=%s/%s user=%s",
                state.count,
                ttft,
                len(text),
                self.agent.agent_type,
                self.agent.id,
                self.user_id,
            )
            return
        if state.stream_chunks % 25 == 0:
            elapsed = time.monotonic() - state.started_at_monotonic
            logger.info(
                "[llm.stream] call #%d elapsed=%.2fs chunks=%d chars=%d\n    agent=%s/%s user=%s",
                state.count,
                elapsed,
                state.stream_chunks,
                state.stream_chars,
                self.agent.agent_type,
                self.agent.id,
                self.user_id,
            )

    def _error_llm_call(self, event: dict[str, Any], state: LLMTraceState) -> None:
        self.cancel_heartbeat(state)
        error = preview_log_value(event_data(event).get("error"))
        logger.warning(
            "[llm.error ] call #%d model=%s provider=%s\n    agent=%s/%s user=%s\n    error: %s",
            state.count,
            self.model_name,
            self.provider_name,
            self.agent.agent_type,
            self.agent.id,
            self.user_id,
            error,
        )
        self._reset_call_state(state)

    def _end_llm_call(self, event: dict[str, Any], state: LLMTraceState) -> None:
        if state.started_at_monotonic is None or state.started_at_wall is None:
            return
        output = event_data(event).get("output")
        state.token_usage.merge(extract_token_usage(output))
        usage = self._build_usage_event(state)
        if usage is not None:
            self.usage_events.append(usage)
        self.cancel_heartbeat(state)
        self._log_llm_end_or_slow(state)
        self._reset_call_state(state)

    def _build_usage_event(self, state: LLMTraceState) -> LLMUsageEvent | None:
        if state.started_at_monotonic is None or state.started_at_wall is None:
            return None
        completed_at = datetime.now(timezone.utc)
        duration_ms = int((time.monotonic() - state.started_at_monotonic) * 1000)
        return LLMUsageEvent(
            user_id=self.user_id,
            agent_id=self.agent.id,
            provider=self.provider_name,
            model=self.model_name,
            run_id=state.run_id,
            llm_call_index=state.count,
            input_tokens=state.token_usage.input_tokens,
            output_tokens=state.token_usage.output_tokens,
            total_tokens=state.token_usage.total_tokens,
            stream_chunks=state.stream_chunks,
            stream_chars=state.stream_chars,
            started_at=state.started_at_wall,
            completed_at=completed_at,
            duration_ms=duration_ms,
        )

    def _log_llm_end_or_slow(self, state: LLMTraceState) -> None:
        if state.started_at_monotonic is None:
            return
        elapsed = time.monotonic() - state.started_at_monotonic
        if not settings.is_development and elapsed <= 30.0:
            return
        ttft: float | None = None
        if state.first_token_at_monotonic is not None:
            ttft = state.first_token_at_monotonic - state.started_at_monotonic
        is_slow = elapsed > 30.0
        log_fn = logger.warning if is_slow else logger.info
        tag = "[llm.slow  ]" if is_slow else "[llm.end   ]"
        log_fn(
            "%s call #%d elapsed=%.2fs ttft=%s chunks=%d chars=%d tokens(in=%s out=%s total=%s)\n"
            "    agent=%s/%s user=%s",
            tag,
            state.count,
            elapsed,
            f"{ttft:.2f}s" if ttft is not None else "n/a(no_stream_token)",
            state.stream_chunks,
            state.stream_chars,
            state.token_usage.input_tokens if state.token_usage.input_tokens is not None else "n/a",
            state.token_usage.output_tokens if state.token_usage.output_tokens is not None else "n/a",
            state.token_usage.total_tokens if state.token_usage.total_tokens is not None else "n/a",
            self.agent.agent_type,
            self.agent.id,
            self.user_id,
        )

    def _log_tool_event(self, event: dict[str, Any]) -> None:
        if not settings.is_development:
            return
        event_name = event.get("event")
        tool_name = event.get("name")
        run_id = event.get("run_id")
        context_line = f"agent={self.agent.agent_type}/{self.agent.id} user={self.user_id} run={run_id}"
        data = event_data(event)
        if event_name == "on_tool_start":
            logger.info(
                "[tool.start] %s\n    %s\n    input:  %s",
                tool_name,
                context_line,
                preview_log_value(data.get("input")),
            )
        elif event_name == "on_tool_end":
            logger.info(
                "[tool.end  ] %s\n    %s\n    output: %s",
                tool_name,
                context_line,
                preview_log_value(data.get("output")),
            )
        elif event_name == "on_tool_error":
            logger.warning(
                "[tool.error] %s\n    %s\n    error:  %s",
                tool_name,
                context_line,
                preview_log_value(data.get("error")),
            )

    async def llm_heartbeat(self, state: LLMTraceState, interval_s: float = 10.0) -> None:
        while True:
            await asyncio.sleep(interval_s)
            if state.started_at_monotonic is None:
                return
            elapsed = time.monotonic() - state.started_at_monotonic
            phase = "waiting_first_token" if state.first_token_at_monotonic is None else "streaming_response"
            logger.info(
                "[llm.wait  ] call #%d elapsed=%.1fs phase=%s chunks=%d chars=%d\n    agent=%s/%s user=%s",
                state.count,
                elapsed,
                phase,
                state.stream_chunks,
                state.stream_chars,
                self.agent.agent_type,
                self.agent.id,
                self.user_id,
            )

    def cancel_heartbeat(self, state: LLMTraceState) -> None:
        if state.heartbeat is not None and not state.heartbeat.done():
            state.heartbeat.cancel()
        state.heartbeat = None

    def _reset_call_state(self, state: LLMTraceState) -> None:
        state.run_id = None
        state.started_at_monotonic = None
        state.started_at_wall = None
        state.first_token_at_monotonic = None
        state.stream_chunks = 0
        state.stream_chars = 0
        state.token_usage = TokenUsage()
