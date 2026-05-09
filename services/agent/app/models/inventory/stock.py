from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.inventory.base import ListMetadata, MovementType


class InventoryLocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    company_id: str
    name: str
    description: str | None = None
    is_default: bool = False


class InventoryLocationListResponse(ListMetadata):
    locations: list[InventoryLocationResponse] = Field(default_factory=list)


class StockMovementCreate(BaseModel):
    company_id: str
    item_id: str
    location_id: str
    movement_type: MovementType
    quantity_delta: Decimal
    reason: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    source_line_id: str | None = None


class StockMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    company_id: str
    item_id: str
    location_id: str
    movement_type: MovementType
    quantity_delta: Decimal
    reason: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    source_line_id: str | None = None
    occurred_at: datetime | None = None


class StockMovementListResponse(ListMetadata):
    movements: list[StockMovementResponse] = Field(default_factory=list)


class StockLevel(BaseModel):
    item_id: str
    item_name: str
    item_sku: str
    location_id: str
    location_name: str
    available_quantity: Decimal
    unit: str


class StockLevelListResponse(BaseModel):
    total_stock_level_count: int = Field(ge=0)
    unique_item_count: int = Field(ge=0)
    returned_count: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
    truncated: bool
    next_offset: int | None = Field(default=None, ge=0)
    levels: list[StockLevel] = Field(default_factory=list)
