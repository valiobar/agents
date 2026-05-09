from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_inventory_service, get_user_id
from app.inventory.models import StockLevelFilters, StockLevelListResponse
from app.inventory.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory/levels", tags=["inventory-levels"])


@router.get("", response_model=StockLevelListResponse)
async def get_stock_levels(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    company_id: Annotated[str, Query(min_length=1)],
    item_id: str | None = None,
    location_id: str | None = None,
    below_reorder_point: bool = False,
    min_available_quantity: Annotated[Decimal | None, Query(ge=0)] = None,
    max_available_quantity: Annotated[Decimal | None, Query(ge=0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort_direction: Literal["asc", "desc"] = "desc",
):
    filters = StockLevelFilters(
        company_id=company_id,
        item_id=item_id,
        location_id=location_id,
        below_reorder_point=below_reorder_point,
        min_available_quantity=min_available_quantity,
        max_available_quantity=max_available_quantity,
        limit=limit,
        offset=offset,
        sort_direction=sort_direction,
    )
    return await service.get_stock_levels(user_id, filters)
