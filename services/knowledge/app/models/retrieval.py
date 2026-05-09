from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.document import ChunkMetadata


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    user_id: str | None = None
    company_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    include_global_tax: bool = True
    include_global_inventory: bool = False
    include_user_documents: bool = True
    allow_legacy_all_company_documents: bool = False
    filters: dict[str, str | int | float | bool] = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
    text: str
    score: float
    collection: str
    metadata: ChunkMetadata


class RetrievalResponse(BaseModel):
    query: str
    chunks: list[RetrievedChunk]

