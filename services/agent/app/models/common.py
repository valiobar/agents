from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ListEnvelope(BaseModel, Generic[T]):
    total_count: int = Field(ge=0)
    returned_count: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
    truncated: bool
    next_offset: int | None = None
    items: list[T]
