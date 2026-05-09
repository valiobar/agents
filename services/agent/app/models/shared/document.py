from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

DocumentStatus = Literal["processing", "ready", "failed", "deleted"]


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
