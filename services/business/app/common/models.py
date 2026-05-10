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


def make_list_envelope(
    items: list[T],
    total_count: int,
    offset: int,
    limit: int,
) -> ListEnvelope[T]:
    returned_count = len(items)
    next_offset = offset + returned_count if (offset + returned_count) < total_count else None
    return ListEnvelope(
        total_count=total_count,
        returned_count=returned_count,
        offset=offset,
        limit=limit,
        truncated=next_offset is not None,
        next_offset=next_offset,
        items=items,
    )
