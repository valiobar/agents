from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DocumentStatus(StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class ChunkMetadata(BaseModel):
    document_id: str
    user_id: str | None = None
    company_id: str | None = None
    filename: str
    chunk_index: int
    source: str = "upload"
    page_number: int | None = None
    content_hash: str


class DocumentCreate(BaseModel):
    company_id: str
    filename: str
    content_type: str
    size_bytes: int
    content_hash: str


class DocumentUpdate(BaseModel):
    filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    content_hash: str | None = None
    status: DocumentStatus | None = None
    error_message: str | None = None
    chunk_count: int | None = None


class DocumentInDB(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    company_id: str
    filename: str
    content_type: str
    size_bytes: int
    content_hash: str
    status: DocumentStatus = DocumentStatus.PROCESSING
    chunk_count: int = 0
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = {"populate_by_name": True}


class DocumentResponse(BaseModel):
    id: str
    company_id: str
    filename: str
    content_type: str
    size_bytes: int
    status: DocumentStatus
    chunk_count: int
    created_at: datetime
    updated_at: datetime

