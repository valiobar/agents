from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import BaseTool

from app.models.shared.conversation import MessageSchema
from app.runtime.usage import LLMUsageEvent

RunMetadata = dict[str, Any]
PreparedTools = list[BaseTool]


@dataclass(slots=True)
class AgentRunInput:
    message: str
    history: list[MessageSchema]
    metadata: RunMetadata = field(default_factory=dict)


@dataclass(slots=True)
class AgentRunEvent:
    name: str | None
    event: str | None
    run_id: str | None
    raw: dict[str, Any]
    metadata: RunMetadata

    @classmethod
    def from_raw(cls, raw: dict[str, Any], metadata: RunMetadata) -> "AgentRunEvent":
        return cls(
            name=raw.get("name") if isinstance(raw.get("name"), str) else None,
            event=raw.get("event") if isinstance(raw.get("event"), str) else None,
            run_id=raw.get("run_id") if isinstance(raw.get("run_id"), str) else None,
            raw=raw,
            metadata=metadata,
        )


@dataclass(slots=True)
class AgentRunChunk:
    text: str
    event: AgentRunEvent
    metadata: RunMetadata


@dataclass(slots=True)
class AgentRunResult:
    emitted_text: bool
    final_output: str
    output_chars: int
    usage_events: list[LLMUsageEvent]
    metadata: RunMetadata
