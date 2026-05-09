from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_inventory_reporting_service, get_user_id
from app.inventory.models import (
    InventoryMovementSummaryResponse,
    InventoryOverviewResponse,
    NegativeStockResponse,
    ReorderReportResponse,
    StockByCategoryResponse,
)
from app.inventory.services.inventory_reporting_service import InventoryReportingService

router = APIRouter(prefix="/inventory/reports", tags=["inventory-reports"])


@router.get("/overview", response_model=InventoryOverviewResponse)
async def get_inventory_overview(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryReportingService, Depends(get_inventory_reporting_service)],
    company_id: Annotated[str, Query(min_length=1)],
):
    return await service.get_overview(user_id, company_id)


@router.get("/reorder", response_model=ReorderReportResponse)
async def get_reorder_report(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryReportingService, Depends(get_inventory_reporting_service)],
    company_id: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return await service.get_reorder_report(user_id, company_id, limit=limit, offset=offset)


@router.get("/stock-by-category", response_model=StockByCategoryResponse)
async def get_stock_by_category(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryReportingService, Depends(get_inventory_reporting_service)],
    company_id: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return await service.get_stock_by_category(user_id, company_id, limit=limit, offset=offset)


@router.get("/negative-stock", response_model=NegativeStockResponse)
async def get_negative_stock(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryReportingService, Depends(get_inventory_reporting_service)],
    company_id: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return await service.list_negative_stock(user_id, company_id, limit=limit, offset=offset)


@router.get("/movement-summary", response_model=InventoryMovementSummaryResponse)
async def get_movement_summary(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryReportingService, Depends(get_inventory_reporting_service)],
    company_id: Annotated[str, Query(min_length=1)],
    group_by: Literal["day", "item", "movement_type"] = "day",
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
):
    return await service.get_movement_summary(
        user_id,
        company_id,
        group_by=group_by,
        limit=limit,
    )
