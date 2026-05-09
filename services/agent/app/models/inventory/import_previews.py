from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.inventory.base import ImportPreviewStatus, ListMetadata


class InventoryImportPreviewLineData(BaseModel):
    candidate: dict
    matched_item_id: str | None = None
    proposed_item: dict | None = None
    location_id: str
    receipt_quantity: Decimal
    warnings: list[str] = Field(default_factory=list)


class InventoryImportPreviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    company_id: str
    document_id: str | None = None
    source_type: str
    status: ImportPreviewStatus
    lines: list[InventoryImportPreviewLineData] = Field(default_factory=list)


class InventoryImportPreviewListResponse(ListMetadata):
    previews: list[InventoryImportPreviewResponse] = Field(default_factory=list)


class InventoryImportResult(BaseModel):
    preview_id: str
    items_created: int
    items_updated: int
    movements_created: int
