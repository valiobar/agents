from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_inventory_service, get_user_id
from app.inventory.models import InventoryCategoryListResponse
from app.inventory.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory/categories", tags=["inventory-categories"])


@router.get("", response_model=InventoryCategoryListResponse)
async def list_categories(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryService, Depends(get_inventory_service)],
    company_id: Annotated[str, Query(min_length=1)],
):
    return await service.list_categories(user_id, company_id)
