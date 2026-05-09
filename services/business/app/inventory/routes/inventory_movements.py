from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_inventory_service, get_user_id
from app.inventory.models import (
    MovementType,
    StockMovementCreate,
    StockMovementFilters,
    StockMovementListResponse,
    StockMovementResponse,
)
from app.inventory.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory/movements", tags=["inventory-movements"])


@router.post("", response_model=StockMovementResponse, status_code=status.HTTP_201_CREATED)
async def create_movement(
    payload: StockMovementCreate,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    movement = await service.create_movement(user_id, payload)
    return StockMovementResponse.model_validate(movement)


@router.get("", response_model=StockMovementListResponse)
async def list_movements(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    company_id: Annotated[str, Query(min_length=1)],
    item_id: str | None = None,
    location_id: str | None = None,
    movement_type: MovementType | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    filters = StockMovementFilters(
        company_id=company_id,
        item_id=item_id,
        location_id=location_id,
        movement_type=movement_type,
    )
    return await service.list_movements(user_id, filters, limit, offset)
