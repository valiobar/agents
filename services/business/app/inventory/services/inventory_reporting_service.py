from __future__ import annotations

from decimal import Decimal
from typing import Literal

from fastapi import HTTPException, status

from app.company.services.company_service import CompanyService
from app.inventory.models import (
    InventoryItemDetailsResponse,
    InventoryItemResponse,
    InventoryMovementSummaryResponse,
    InventoryOverviewResponse,
    NegativeStockResponse,
    ReorderReportResponse,
    StockByCategoryResponse,
    StockLevel,
    StockLevelFilters,
    StockMovementFilters,
    StockMovementResponse,
    page_response,
)
from app.inventory.repositories.inventory_item_repo import InventoryItemRepository
from app.inventory.repositories.inventory_location_repo import InventoryLocationRepository
from app.inventory.repositories.stock_movement_repo import StockMovementRepository


class InventoryReportingService:
    def __init__(
        self,
        item_repo: InventoryItemRepository,
        location_repo: InventoryLocationRepository,
        movement_repo: StockMovementRepository,
        company_service: CompanyService,
    ) -> None:
        self.item_repo = item_repo
        self.location_repo = location_repo
        self.movement_repo = movement_repo
        self.company_service = company_service

    async def get_overview(self, user_id: str, company_id: str) -> InventoryOverviewResponse:
        await self.company_service.require_company(user_id, company_id)
        item_counts = await self.item_repo.count_statuses(user_id, company_id)
        category_count = await self.item_repo.count_categories(user_id, company_id)
        location_count = await self.location_repo.count_by_company(user_id, company_id)
        low_stock_count, negative_stock_count = await self.movement_repo.count_low_and_negative_stock(
            user_id, company_id
        )
        return InventoryOverviewResponse(
            total_item_count=item_counts.total,
            active_item_count=item_counts.active,
            inactive_item_count=item_counts.inactive,
            category_count=category_count,
            location_count=location_count,
            low_stock_count=low_stock_count,
            negative_stock_count=negative_stock_count,
        )

    async def get_reorder_report(
        self,
        user_id: str,
        company_id: str,
        *,
        limit: int,
        offset: int,
    ) -> ReorderReportResponse:
        await self.company_service.require_company(user_id, company_id)
        rows, total_count = await self.movement_repo.reorder_report(
            user_id,
            company_id,
            limit=limit,
            offset=offset,
        )
        return ReorderReportResponse(
            **page_response(total_count=total_count, offset=offset, limit=limit, rows=rows),
            rows=rows,
        )

    async def get_stock_by_category(
        self,
        user_id: str,
        company_id: str,
        *,
        limit: int,
        offset: int,
    ) -> StockByCategoryResponse:
        await self.company_service.require_company(user_id, company_id)
        rows, total_count = await self.movement_repo.stock_by_category(
            user_id,
            company_id,
            limit=limit,
            offset=offset,
        )
        return StockByCategoryResponse(
            **page_response(total_count=total_count, offset=offset, limit=limit, rows=rows),
            rows=rows,
        )

    async def list_negative_stock(
        self,
        user_id: str,
        company_id: str,
        *,
        limit: int,
        offset: int,
    ) -> NegativeStockResponse:
        await self.company_service.require_company(user_id, company_id)
        raw_levels, total_count = await self.movement_repo.negative_stock_levels(
            user_id,
            company_id,
            limit=limit,
            offset=offset,
        )
        levels = await self._hydrate_stock_levels(user_id, company_id, raw_levels)
        return NegativeStockResponse(
            **page_response(total_count=total_count, offset=offset, limit=limit, rows=levels),
            levels=levels,
        )

    async def get_item_details(
        self,
        user_id: str,
        company_id: str,
        item_id: str,
        *,
        recent_movements_limit: int,
    ) -> InventoryItemDetailsResponse:
        await self.company_service.require_company(user_id, company_id)
        item = await self.item_repo.get_by_id(user_id, company_id, item_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found")

        quantities = await self.movement_repo.aggregate_available_quantities(user_id, company_id, [item_id])
        item_response = InventoryItemResponse(
            **item.model_dump(mode="python"),
            available_in_stock=quantities.get(item_id, Decimal("0")),
        )

        raw_levels, _, _ = await self.movement_repo.aggregate_levels_by_location(
            user_id=user_id,
            filters=StockLevelFilters(
                company_id=company_id,
                item_id=item_id,
                limit=100,
                offset=0,
                sort_direction="desc",
            ),
        )
        stock_levels = await self._hydrate_stock_levels(user_id, company_id, raw_levels)

        recent_movements_raw = await self.movement_repo.list_by_filters(
            user_id,
            StockMovementFilters(company_id=company_id, item_id=item_id),
            limit=recent_movements_limit,
            offset=0,
        )
        recent_movements = [
            StockMovementResponse.model_validate(movement.model_dump(mode="python"))
            for movement in recent_movements_raw
        ]
        return InventoryItemDetailsResponse(
            item=item_response,
            stock_levels=stock_levels,
            recent_movements=recent_movements,
        )

    async def get_movement_summary(
        self,
        user_id: str,
        company_id: str,
        *,
        group_by: Literal["day", "item", "movement_type"],
        limit: int,
    ) -> InventoryMovementSummaryResponse:
        await self.company_service.require_company(user_id, company_id)
        rows = await self.movement_repo.summarize_movements(
            user_id,
            company_id,
            group_by=group_by,
            limit=limit,
        )
        return InventoryMovementSummaryResponse(company_id=company_id, group_by=group_by, rows=rows)

    async def _hydrate_stock_levels(
        self,
        user_id: str,
        company_id: str,
        raw_levels: list[dict[str, str | Decimal]],
    ) -> list[StockLevel]:
        if not raw_levels:
            return []
        item_ids = list({str(level["item_id"]) for level in raw_levels})
        location_ids = list({str(level["location_id"]) for level in raw_levels})
        items_map = await self.item_repo.get_many_by_ids(user_id, company_id, item_ids)
        locations_map = await self.location_repo.get_many_by_ids(user_id, company_id, location_ids)

        levels: list[StockLevel] = []
        for raw in raw_levels:
            item_id = str(raw["item_id"])
            location_id = str(raw["location_id"])
            item = items_map.get(item_id)
            location = locations_map.get(location_id)
            if item is None or location is None:
                continue
            quantity = raw["available_quantity"]
            if not isinstance(quantity, Decimal):
                quantity = Decimal(str(quantity))
            levels.append(
                StockLevel(
                    item_id=item_id,
                    item_name=item.name,
                    item_sku=item.sku,
                    location_id=location_id,
                    location_name=location.name,
                    available_quantity=quantity,
                    unit=item.unit,
                )
            )
        return levels
