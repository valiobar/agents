from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class TokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    @property
    def has_any(self) -> bool:
        return self.input_tokens is not None or self.output_tokens is not None or self.total_tokens is not None

    def merge(self, other: "TokenUsage") -> None:
        if other.input_tokens is not None:
            self.input_tokens = other.input_tokens
        if other.output_tokens is not None:
            self.output_tokens = other.output_tokens
        if other.total_tokens is not None:
            self.total_tokens = other.total_tokens


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_int(*values: Any) -> int | None:
    for value in values:
        parsed = _int_or_none(value)
        if parsed is not None:
            return parsed
    return None


def extract_token_usage(message_or_chunk: Any) -> TokenUsage:
    usage_metadata = _as_dict(getattr(message_or_chunk, "usage_metadata", None))
    response_metadata = _as_dict(getattr(message_or_chunk, "response_metadata", None))
    token_usage = _as_dict(response_metadata.get("token_usage"))
    response_usage = _as_dict(response_metadata.get("usage"))

    return TokenUsage(
        input_tokens=_first_int(
            usage_metadata.get("input_tokens"),
            usage_metadata.get("prompt_tokens"),
            token_usage.get("prompt_tokens"),
            token_usage.get("input_tokens"),
            response_usage.get("input_tokens"),
            response_usage.get("prompt_tokens"),
        ),
        output_tokens=_first_int(
            usage_metadata.get("output_tokens"),
            usage_metadata.get("completion_tokens"),
            token_usage.get("completion_tokens"),
            token_usage.get("output_tokens"),
            response_usage.get("output_tokens"),
            response_usage.get("completion_tokens"),
        ),
        total_tokens=_first_int(
            usage_metadata.get("total_tokens"),
            token_usage.get("total_tokens"),
            response_usage.get("total_tokens"),
        ),
    )


@dataclass(frozen=True, slots=True)
class LLMUsageEvent:
    user_id: str
    agent_id: str
    provider: str
    model: str
    run_id: str | None
    llm_call_index: int
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    stream_chunks: int
    stream_chars: int
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    source: str = "agent_runtime"
