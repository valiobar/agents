from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import get_inventory_search_service, get_user_id
from app.inventory.models import (
    InventorySearchRequest,
    InventorySearchResponse,
    ResolveInventoryItemRequest,
    ResolveInventoryItemResponse,
)
from app.inventory.services.inventory_search_service import InventorySearchService

router = APIRouter(prefix="/inventory", tags=["inventory-search"])


@router.post("/search", response_model=InventorySearchResponse)
async def search_inventory(
    payload: InventorySearchRequest,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventorySearchService, Depends(get_inventory_search_service)],
):
    return await service.search(user_id, payload)


@router.post("/resolve-item", response_model=ResolveInventoryItemResponse)
async def resolve_inventory_item(
    payload: ResolveInventoryItemRequest,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventorySearchService, Depends(get_inventory_search_service)],
):
    return await service.resolve_item(user_id, payload)
