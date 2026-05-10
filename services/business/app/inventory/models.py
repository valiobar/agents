from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


MovementType = Literal["receipt", "issue", "adjustment", "transfer_in", "transfer_out", "return"]
ImportPreviewStatus = Literal["draft", "confirmed", "cancelled"]
ImportSourceType = Literal["supplier_invoice_upload", "agent"]
SearchMatchReason = Literal["sku", "barcode", "alias", "text", "prefix"]


class InventoryMoneyModel(BaseModel):
    @field_serializer("*", when_used="json")
    def serialize_decimal(self, value, _info):
        if isinstance(value, Decimal):
            return str(value)
        return value


class InventoryItemCreate(InventoryMoneyModel):
    company_id: str = Field(min_length=1, max_length=64)
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, max_length=120)
    barcode: str | None = Field(default=None, max_length=128)
    aliases: list[str] = Field(default_factory=list)
    unit: str = Field(min_length=1, max_length=32)
    selling_price: Decimal | None = Field(default=None, ge=0)
    reorder_point: Decimal | None = Field(default=None, ge=0)
    target_stock_level: Decimal | None = Field(default=None, ge=0)
    supplier_partner_id: str | None = Field(default=None, max_length=64)
    is_active: bool = True


class InventoryItemUpdate(InventoryMoneyModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, max_length=120)
    barcode: str | None = Field(default=None, max_length=128)
    aliases: list[str] | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=32)
    selling_price: Decimal | None = Field(default=None, ge=0)
    reorder_point: Decimal | None = Field(default=None, ge=0)
    target_stock_level: Decimal | None = Field(default=None, ge=0)
    supplier_partner_id: str | None = Field(default=None, max_length=64)
    is_active: bool | None = None


class InventoryItemInDB(InventoryMoneyModel):
    id: str
    user_id: str
    created_by_user_id: str
    updated_by_user_id: str
    company_id: str
    sku: str
    name: str
    description: str | None = None
    category: str | None = None
    barcode: str | None = None
    aliases: list[str] = Field(default_factory=list)
    search_text: str = ""
    unit: str
    selling_price: Decimal | None = None
    reorder_point: Decimal | None = None
    target_stock_level: Decimal | None = None
    supplier_partner_id: str | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class InventoryItemResponse(InventoryItemInDB):
    model_config = ConfigDict(from_attributes=True)
    available_in_stock: Decimal | None = None


class InventoryCategorySummary(BaseModel):
    category: str
    item_count: int = Field(ge=0)
    active_item_count: int = Field(ge=0)


class InventoryCategoryListResponse(BaseModel):
    total_category_count: int = Field(ge=0)
    uncategorized_item_count: int = Field(ge=0)
    categories: list[InventoryCategorySummary] = Field(default_factory=list)


class ListMetadata(BaseModel):
    total_count: int = Field(ge=0)
    returned_count: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
    truncated: bool
    next_offset: int | None = Field(default=None, ge=0)


def page_response(total_count: int, offset: int, limit: int, rows: list[Any]) -> dict[str, Any]:
    returned_count = len(rows)
    next_offset = offset + returned_count if (offset + returned_count) < total_count else None
    return {
        "total_count": total_count,
        "returned_count": returned_count,
        "offset": offset,
        "limit": limit,
        "truncated": next_offset is not None,
        "next_offset": next_offset,
    }


class InventoryItemFilters(BaseModel):
    company_id: str
    category: str | None = None
    is_active: bool | None = None
    search: str | None = None
    sku: str | None = None
    barcode: str | None = None


class InventoryLocationCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    is_default: bool = False


class InventoryLocationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    is_default: bool | None = None


class InventoryLocationInDB(BaseModel):
    id: str
    user_id: str
    company_id: str
    name: str
    description: str | None = None
    is_default: bool = False
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class InventoryLocationResponse(InventoryLocationInDB):
    model_config = ConfigDict(from_attributes=True)


class InventoryLocationListResponse(ListMetadata):
    locations: list[InventoryLocationResponse] = Field(default_factory=list)


class StockMovementCreate(InventoryMoneyModel):
    company_id: str = Field(min_length=1, max_length=64)
    item_id: str = Field(min_length=1, max_length=64)
    location_id: str = Field(min_length=1, max_length=64)
    movement_type: MovementType
    quantity_delta: Decimal
    reason: str | None = Field(default=None, max_length=500)
    source_type: str | None = Field(default=None, max_length=64)
    source_id: str | None = Field(default=None, max_length=64)
    source_line_id: str | None = Field(default=None, max_length=64)

    @classmethod
    def receipt_from_import(
        cls,
        preview_id: str,
        company_id: str,
        item_id: str,
        location_id: str,
        quantity: Decimal,
        line_index: int,
    ) -> "StockMovementCreate":
        return cls(
            company_id=company_id,
            item_id=item_id,
            location_id=location_id,
            movement_type="receipt",
            quantity_delta=quantity,
            reason="Supplier invoice import",
            source_type="supplier_invoice_import",
            source_id=preview_id,
            source_line_id=str(line_index),
        )

    @classmethod
    def issue_from_invoice(
        cls,
        company_id: str,
        invoice_id: str,
        item_id: str,
        location_id: str,
        quantity: Decimal,
        line_index: int,
    ) -> "StockMovementCreate":
        return cls(
            company_id=company_id,
            item_id=item_id,
            location_id=location_id,
            movement_type="issue",
            quantity_delta=-abs(quantity),
            reason="Invoice stock deduction",
            source_type="invoice",
            source_id=invoice_id,
            source_line_id=str(line_index),
        )


class StockMovementInDB(InventoryMoneyModel):
    id: str
    user_id: str
    performed_by_user_id: str
    company_id: str
    item_id: str
    location_id: str
    movement_type: MovementType
    quantity_delta: Decimal
    reason: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    source_line_id: str | None = None
    occurred_at: datetime = Field(default_factory=_utc_now)
    created_at: datetime = Field(default_factory=_utc_now)


class StockMovementResponse(StockMovementInDB):
    model_config = ConfigDict(from_attributes=True)


class StockMovementListResponse(ListMetadata):
    movements: list[StockMovementResponse] = Field(default_factory=list)


class StockMovementFilters(BaseModel):
    company_id: str
    item_id: str | None = None
    location_id: str | None = None
    movement_type: MovementType | None = None


class StockLevel(InventoryMoneyModel):
    item_id: str
    item_name: str
    item_sku: str
    location_id: str
    location_name: str
    available_quantity: Decimal
    unit: str


class StockLevelFilters(BaseModel):
    company_id: str
    item_id: str | None = None
    location_id: str | None = None
    below_reorder_point: bool = False
    min_available_quantity: Decimal | None = Field(default=None, ge=0)
    max_available_quantity: Decimal | None = Field(default=None, ge=0)
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)
    sort_direction: Literal["asc", "desc"] = "desc"


class StockLevelListResponse(BaseModel):
    total_stock_level_count: int = Field(ge=0)
    unique_item_count: int = Field(ge=0)
    returned_count: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
    truncated: bool
    next_offset: int | None = Field(default=None, ge=0)
    levels: list[StockLevel] = Field(default_factory=list)


class InventoryItemStatusCounts(BaseModel):
    total: int = Field(ge=0)
    active: int = Field(ge=0)
    inactive: int = Field(ge=0)


class InventoryOverviewResponse(BaseModel):
    total_item_count: int = Field(ge=0)
    active_item_count: int = Field(ge=0)
    inactive_item_count: int = Field(ge=0)
    category_count: int = Field(ge=0)
    location_count: int = Field(ge=0)
    low_stock_count: int = Field(ge=0)
    negative_stock_count: int = Field(ge=0)


class ReorderReportRow(InventoryMoneyModel):
    item_id: str
    item_name: str
    sku: str
    location_id: str
    location_name: str
    available_quantity: Decimal
    reorder_point: Decimal
    target_stock_level: Decimal | None = None
    suggested_reorder_quantity: Decimal | None = None
    supplier_partner_id: str | None = None


class ReorderReportResponse(ListMetadata):
    rows: list[ReorderReportRow] = Field(default_factory=list)


class StockByCategoryRow(InventoryMoneyModel):
    category: str | None = None
    item_count: int = Field(ge=0)
    total_available_quantity: Decimal


class StockByCategoryResponse(ListMetadata):
    rows: list[StockByCategoryRow] = Field(default_factory=list)


class NegativeStockResponse(ListMetadata):
    levels: list[StockLevel] = Field(default_factory=list)


class InventoryItemDetailsResponse(BaseModel):
    item: InventoryItemResponse
    stock_levels: list[StockLevel] = Field(default_factory=list)
    recent_movements: list[StockMovementResponse] = Field(default_factory=list)


class InventoryMovementSummaryRow(InventoryMoneyModel):
    label: str
    movement_count: int = Field(ge=0)
    total_quantity_delta: Decimal


class InventoryMovementSummaryResponse(BaseModel):
    company_id: str
    group_by: Literal["day", "item", "movement_type"]
    rows: list[InventoryMovementSummaryRow] = Field(default_factory=list)


class InventorySearchRequest(BaseModel):
    company_id: str = Field(min_length=1, max_length=64)
    query: str = Field(min_length=1, max_length=500)
    include_stock: bool = True
    min_confidence: float = Field(default=0.70, ge=0, le=1)
    limit: int = Field(default=20, ge=1, le=100)


class InventorySearchMatch(InventoryMoneyModel):
    item_id: str
    name: str
    description: str | None = None
    sku: str | None = None
    category: str | None = None
    unit: str
    selling_price: Decimal | None = None
    confidence: float
    match_reason: SearchMatchReason
    available_quantity: Decimal | None = None


class InventorySearchResponse(InventoryMoneyModel):
    query: str
    normalized_query: str
    matches: list[InventorySearchMatch]
    total_available_quantity: Decimal | None = None
    message: str | None = None


class ResolveInventoryItemRequest(BaseModel):
    company_id: str = Field(min_length=1, max_length=64)
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)


class ResolveInventoryItemResponse(InventoryMoneyModel):
    query: str
    normalized_query: str
    exact_match: InventorySearchMatch | None = None
    candidates: list[InventorySearchMatch] = Field(default_factory=list)
    message: str | None = None


class InventoryItemListResponse(ListMetadata):
    items: list[InventoryItemResponse] = Field(default_factory=list)


class SupplierInvoiceLineCandidate(InventoryMoneyModel):
    description: str = Field(min_length=1, max_length=500)
    sku: str | None = Field(default=None, max_length=64)
    barcode: str | None = Field(default=None, max_length=128)
    quantity: Decimal = Field(gt=0)
    unit: str | None = Field(default=None, max_length=32)
    unit_price: Decimal | None = Field(default=None, ge=0)


class InventoryImportPreviewLineCreate(InventoryMoneyModel):
    candidate: SupplierInvoiceLineCandidate
    matched_item_id: str | None = None
    proposed_item: InventoryItemCreate | None = None
    location_id: str = Field(min_length=1, max_length=64)
    receipt_quantity: Decimal = Field(gt=0)
    warnings: list[str] = Field(default_factory=list)


class InventoryImportPreviewLine(InventoryImportPreviewLineCreate):
    pass


class InventoryImportPreviewCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=64)
    document_id: str | None = Field(default=None, max_length=64)
    source_type: ImportSourceType = "supplier_invoice_upload"
    lines: list[SupplierInvoiceLineCandidate] = Field(min_length=1)


class InventoryImportPreviewInDB(BaseModel):
    id: str
    user_id: str
    company_id: str
    document_id: str | None = None
    source_type: ImportSourceType
    status: ImportPreviewStatus = "draft"
    lines: list[InventoryImportPreviewLine] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class InventoryImportPreviewResponse(InventoryImportPreviewInDB):
    model_config = ConfigDict(from_attributes=True)


class InventoryImportPreviewListResponse(ListMetadata):
    previews: list[InventoryImportPreviewResponse] = Field(default_factory=list)


class InventoryImportPreviewUpdate(BaseModel):
    lines: list[InventoryImportPreviewLineCreate] | None = None


class InventoryImportResult(BaseModel):
    preview_id: str
    items_created: int
    items_updated: int
    movements_created: int
