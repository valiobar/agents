from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_inventory_reporting_service, get_inventory_service, get_user_id
from app.inventory.models import (
    InventoryItemDetailsResponse,
    InventoryItemCreate,
    InventoryItemFilters,
    InventoryItemListResponse,
    InventoryItemResponse,
    InventoryItemUpdate,
)
from app.inventory.services.inventory_reporting_service import InventoryReportingService
from app.inventory.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory/items", tags=["inventory-items"])


@router.post("", response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: InventoryItemCreate,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
):
    item = await service.create_item(user_id, payload)
    return InventoryItemResponse.model_validate(item)


@router.get("", response_model=InventoryItemListResponse)
async def list_items(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    company_id: Annotated[str, Query(min_length=1)],
    category: str | None = None,
    is_active: bool | None = None,
    sku: str | None = None,
    barcode: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    filters = InventoryItemFilters(
        company_id=company_id,
        category=category,
        is_active=is_active,
        sku=sku,
        barcode=barcode,
    )
    return await service.list_items(user_id, filters, limit, offset)


@router.get("/{item_id}", response_model=InventoryItemResponse)
async def get_item(
    item_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    company_id: Annotated[str, Query(min_length=1)],
):
    return await service.get_item(user_id, company_id, item_id)


@router.get("/{item_id}/details", response_model=InventoryItemDetailsResponse)
async def get_item_details(
    item_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryReportingService, Depends(get_inventory_reporting_service)],
    company_id: Annotated[str, Query(min_length=1)],
    recent_movements_limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return await service.get_item_details(
        user_id,
        company_id,
        item_id,
        recent_movements_limit=recent_movements_limit,
    )


@router.patch("/{item_id}", response_model=InventoryItemResponse)
async def update_item(
    item_id: str,
    payload: InventoryItemUpdate,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    company_id: Annotated[str, Query(min_length=1)],
):
    item = await service.update_item(user_id, company_id, item_id, payload)
    return InventoryItemResponse.model_validate(item)
