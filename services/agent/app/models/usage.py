from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.runtime.usage import LLMUsageEvent


class UsageEventCreate(BaseModel):
    user_id: str
    agent_id: str
    conversation_id: str
    provider: str
    model: str
    run_id: str | None = None
    llm_call_index: int = Field(ge=1)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    stream_chunks: int = Field(default=0, ge=0)
    stream_chars: int = Field(default=0, ge=0)
    started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(ge=0)
    source: Literal["agent_runtime"] = "agent_runtime"
    created_at: datetime

    @classmethod
    def from_runtime_event(
        cls,
        event: LLMUsageEvent,
        conversation_id: str,
        created_at: datetime,
    ) -> "UsageEventCreate":
        return cls(
            user_id=event.user_id,
            agent_id=event.agent_id,
            conversation_id=conversation_id,
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
            created_at=created_at,
        )

    @property
    def idempotency_key(self) -> str:
        run_part = self.run_id or "no-run-id"
        return f"{self.conversation_id}:{run_part}:{self.llm_call_index}"


class UsageEventInDB(UsageEventCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
