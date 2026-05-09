from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.models.inventory.base import ListMetadata
from app.models.inventory.items import InventoryItemResponse
from app.models.inventory.stock import StockLevel, StockMovementResponse


class InventoryOverviewResponse(BaseModel):
    total_item_count: int = Field(ge=0)
    active_item_count: int = Field(ge=0)
    inactive_item_count: int = Field(ge=0)
    category_count: int = Field(ge=0)
    location_count: int = Field(ge=0)
    low_stock_count: int = Field(ge=0)
    negative_stock_count: int = Field(ge=0)


class ReorderReportRow(BaseModel):
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


class StockByCategoryRow(BaseModel):
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


class InventoryMovementSummaryRow(BaseModel):
    label: str
    movement_count: int = Field(ge=0)
    total_quantity_delta: Decimal


class InventoryMovementSummaryResponse(BaseModel):
    company_id: str
    group_by: Literal["day", "item", "movement_type"]
    rows: list[InventoryMovementSummaryRow] = Field(default_factory=list)
