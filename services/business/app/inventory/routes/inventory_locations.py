from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_inventory_service, get_user_id
from app.inventory.models import (
    InventoryLocationCreate,
    InventoryLocationListResponse,
    InventoryLocationResponse,
    InventoryLocationUpdate,
)
from app.inventory.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory/locations", tags=["inventory-locations"])


@router.post("", response_model=InventoryLocationResponse, status_code=status.HTTP_201_CREATED)
async def create_location(
    payload: InventoryLocationCreate,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    location = await service.create_location(user_id, payload)
    return InventoryLocationResponse.model_validate(location)


@router.get("", response_model=InventoryLocationListResponse)
async def list_locations(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    company_id: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return await service.list_locations(user_id, company_id, limit, offset)


@router.get("/{location_id}", response_model=InventoryLocationResponse)
async def get_location(
    location_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    company_id: Annotated[str, Query(min_length=1)],
):
    location = await service.get_location(user_id, company_id, location_id)
    return InventoryLocationResponse.model_validate(location)


@router.patch("/{location_id}", response_model=InventoryLocationResponse)
async def update_location(
    location_id: str,
    payload: InventoryLocationUpdate,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    company_id: Annotated[str, Query(min_length=1)],
):
    location = await service.update_location(user_id, company_id, location_id, payload)
    return InventoryLocationResponse.model_validate(location)
