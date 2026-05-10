from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.inventory.base import ImportPreviewStatus, ListMetadata
from app.models.inventory.items import InventoryItemCreate

ImportSourceType = Literal["supplier_invoice_upload", "agent"]


class SupplierInvoiceLineCandidate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    sku: str | None = Field(default=None, max_length=64)
    barcode: str | None = Field(default=None, max_length=128)
    quantity: Decimal = Field(gt=0)
    unit: str | None = Field(default=None, max_length=32)
    unit_price: Decimal | None = Field(default=None, ge=0)


class InventoryImportPreviewCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=64)
    document_id: str | None = Field(default=None, max_length=64)
    source_type: ImportSourceType = "supplier_invoice_upload"
    lines: list[SupplierInvoiceLineCandidate] = Field(min_length=1)


class InventoryImportPreviewLineData(BaseModel):
    candidate: SupplierInvoiceLineCandidate
    matched_item_id: str | None = None
    proposed_item: InventoryItemCreate | None = None
    location_id: str
    receipt_quantity: Decimal
    warnings: list[str] = Field(default_factory=list)


class InventoryImportPreviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    company_id: str
    document_id: str | None = None
    source_type: ImportSourceType
    status: ImportPreviewStatus
    lines: list[InventoryImportPreviewLineData] = Field(default_factory=list)


class InventoryImportPreviewListResponse(ListMetadata):
    previews: list[InventoryImportPreviewResponse] = Field(default_factory=list)


class InventoryImportResult(BaseModel):
    preview_id: str
    items_created: int
    items_updated: int
    movements_created: int
