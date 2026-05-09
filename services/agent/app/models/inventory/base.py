from typing import Literal

from pydantic import BaseModel, Field

MovementType = Literal["receipt", "issue", "adjustment", "transfer_in", "transfer_out", "return"]
ImportPreviewStatus = Literal["draft", "confirmed", "cancelled"]
SearchMatchReason = Literal["sku", "barcode", "alias", "text", "prefix"]


class ListMetadata(BaseModel):
    total_count: int = Field(ge=0)
    returned_count: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
    truncated: bool
    next_offset: int | None = Field(default=None, ge=0)
