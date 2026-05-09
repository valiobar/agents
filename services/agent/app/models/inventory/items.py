from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.inventory.base import ListMetadata, SearchMatchReason


class InventoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    company_id: str
    sku: str
    name: str
    description: str | None = None
    category: str | None = None
    barcode: str | None = None
    aliases: list[str] = Field(default_factory=list)
    unit: str
    selling_price: Decimal | None = None
    reorder_point: Decimal | None = None
    target_stock_level: Decimal | None = None
    available_in_stock: Decimal | None = None
    supplier_partner_id: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class InventoryCategorySummary(BaseModel):
    category: str
    item_count: int
    active_item_count: int


class InventoryCategoryListResponse(BaseModel):
    total_category_count: int
    uncategorized_item_count: int
    categories: list[InventoryCategorySummary] = Field(default_factory=list)


class InventoryItemListResponse(ListMetadata):
    items: list[InventoryItemResponse] = Field(default_factory=list)


class InventoryItemCreate(BaseModel):
    company_id: str
    sku: str
    name: str
    description: str | None = None
    category: str | None = None
    barcode: str | None = None
    aliases: list[str] = Field(default_factory=list)
    unit: str
    selling_price: Decimal | None = None
    reorder_point: Decimal | None = None
    target_stock_level: Decimal | None = None
    supplier_partner_id: str | None = None
    is_active: bool = True


class InventoryItemUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    barcode: str | None = None
    aliases: list[str] | None = None
    unit: str | None = None
    selling_price: Decimal | None = None
    reorder_point: Decimal | None = None
    target_stock_level: Decimal | None = None
    supplier_partner_id: str | None = None
    is_active: bool | None = None


class InventorySearchRequest(BaseModel):
    company_id: str
    query: str
    include_stock: bool = True
    min_confidence: float = 0.70
    limit: int = 20


class InventorySearchMatch(BaseModel):
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


class InventorySearchResponse(BaseModel):
    query: str
    normalized_query: str
    matches: list[InventorySearchMatch]
    total_available_quantity: Decimal | None = None
    message: str | None = None


class ResolveInventoryItemRequest(BaseModel):
    company_id: str
    query: str
    limit: int = 5


class ResolveInventoryItemResponse(BaseModel):
    query: str
    normalized_query: str
    exact_match: InventorySearchMatch | None = None
    candidates: list[InventorySearchMatch] = Field(default_factory=list)
    message: str | None = None
