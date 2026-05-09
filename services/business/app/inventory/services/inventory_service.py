from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status

from app.company.services.company_service import CompanyService
from app.inventory.models import (
    InventoryCategoryListResponse,
    InventoryItemCreate,
    InventoryItemFilters,
    InventoryItemInDB,
    InventoryItemListResponse,
    InventoryItemResponse,
    InventoryItemUpdate,
    InventoryLocationCreate,
    InventoryLocationInDB,
    InventoryLocationListResponse,
    InventoryLocationResponse,
    InventoryLocationUpdate,
    StockLevel,
    StockLevelFilters,
    StockLevelListResponse,
    StockMovementCreate,
    StockMovementFilters,
    StockMovementInDB,
    StockMovementListResponse,
    StockMovementResponse,
    page_response,
)
from app.inventory.repositories.inventory_item_repo import InventoryItemRepository
from app.inventory.repositories.inventory_location_repo import InventoryLocationRepository
from app.inventory.repositories.stock_movement_repo import StockMovementRepository


class InventoryService:
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

    async def _attach_available_stock(
        self,
        user_id: str,
        company_id: str,
        items: list[InventoryItemInDB],
    ) -> list[InventoryItemResponse]:
        if not items:
            return []
        item_ids = [item.id for item in items]
        stock_by_item = await self.movement_repo.aggregate_available_quantities(
            user_id=user_id,
            company_id=company_id,
            item_ids=item_ids,
        )
        return [
            InventoryItemResponse(
                **item.model_dump(mode="python"),
                available_in_stock=stock_by_item.get(item.id, Decimal("0")),
            )
            for item in items
        ]

    # --- Items ---

    async def create_item(self, user_id: str, payload: InventoryItemCreate) -> InventoryItemInDB:
        await self.company_service.require_company(user_id, payload.company_id)
        existing = await self.item_repo.find_by_sku(user_id, payload.company_id, payload.sku)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Item with SKU '{payload.sku}' already exists in this company",
            )
        return await self.item_repo.create(user_id, payload, changed_by_user_id=user_id)

    async def get_item(self, user_id: str, company_id: str, item_id: str) -> InventoryItemResponse:
        await self.company_service.require_company(user_id, company_id)
        item = await self.item_repo.get_by_id(user_id, company_id, item_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found")
        enriched = await self._attach_available_stock(user_id, company_id, [item])
        return enriched[0]

    async def update_item(
        self,
        user_id: str,
        company_id: str,
        item_id: str,
        payload: InventoryItemUpdate,
    ) -> InventoryItemInDB:
        await self.company_service.require_company(user_id, company_id)

        updated = await self.item_repo.update(
            user_id,
            company_id,
            item_id,
            payload,
            changed_by_user_id=user_id,
        )
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found")
        return updated

    async def list_items(
        self,
        user_id: str,
        filters: InventoryItemFilters,
        limit: int,
        offset: int,
    ) -> InventoryItemListResponse:
        await self.company_service.require_company(user_id, filters.company_id)
        total_count = await self.item_repo.count_by_filters(user_id, filters)
        items = await self.item_repo.list_by_company(user_id, filters, limit, offset)
        enriched = await self._attach_available_stock(user_id, filters.company_id, items)
        return InventoryItemListResponse(
            **page_response(total_count=total_count, offset=offset, limit=limit, rows=enriched),
            items=enriched,
        )

    async def list_categories(self, user_id: str, company_id: str) -> InventoryCategoryListResponse:
        await self.company_service.require_company(user_id, company_id)
        return await self.item_repo.list_categories(user_id, company_id)

    async def require_item_for_company(
        self,
        user_id: str,
        company_id: str,
        item_id: str,
        location_id: str | None = None,
    ) -> InventoryItemInDB:
        await self.company_service.require_company(user_id, company_id)

        item = await self.item_repo.get_by_id(user_id, company_id, item_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inventory item '{item_id}' not found in this company",
            )

        if location_id is not None:
            location_exists = await self.location_repo.exists(user_id, company_id, location_id)
            if not location_exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Inventory location '{location_id}' not found in this company",
                )

        return item

    # --- Locations ---

    async def create_location(self, user_id: str, payload: InventoryLocationCreate) -> InventoryLocationInDB:
        await self.company_service.require_company(user_id, payload.company_id)
        return await self.location_repo.create(user_id, payload)

    async def get_location(self, user_id: str, company_id: str, location_id: str) -> InventoryLocationInDB:
        await self.company_service.require_company(user_id, company_id)
        location = await self.location_repo.get_by_id(user_id, company_id, location_id)
        if location is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory location not found")
        return location

    async def update_location(
        self,
        user_id: str,
        company_id: str,
        location_id: str,
        payload: InventoryLocationUpdate,
    ) -> InventoryLocationInDB:
        await self.company_service.require_company(user_id, company_id)
        updated = await self.location_repo.update(user_id, company_id, location_id, payload)
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory location not found")
        return updated

    async def list_locations(
        self,
        user_id: str,
        company_id: str,
        limit: int,
        offset: int,
    ) -> InventoryLocationListResponse:
        await self.company_service.require_company(user_id, company_id)
        total_count = await self.location_repo.count_by_company(user_id, company_id)
        locations = await self.location_repo.list_by_company(user_id, company_id, limit, offset)
        location_rows = [InventoryLocationResponse.model_validate(location) for location in locations]
        return InventoryLocationListResponse(
            **page_response(total_count=total_count, offset=offset, limit=limit, rows=location_rows),
            locations=location_rows,
        )

    async def get_or_create_default_location(self, user_id: str, company_id: str) -> InventoryLocationInDB:
        await self.company_service.require_company(user_id, company_id)

        location = await self.location_repo.get_default(user_id, company_id)
        if location:
            return location

        return await self.location_repo.create(
            user_id,
            InventoryLocationCreate(company_id=company_id, name="Default", is_default=True),
        )

    # --- Movements ---

    async def create_movement(self, user_id: str, payload: StockMovementCreate) -> StockMovementInDB:
        await self.company_service.require_company(user_id, payload.company_id)
        await self.require_item_for_company(
            user_id=user_id,
            company_id=payload.company_id,
            item_id=payload.item_id,
            location_id=payload.location_id,
        )

        if payload.source_type and payload.source_id and payload.source_line_id:
            already_exists = await self.movement_repo.has_source_movement(
                user_id=user_id,
                source_type=payload.source_type,
                source_id=payload.source_id,
                source_line_id=payload.source_line_id,
            )
            if already_exists:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Stock movement already exists for this source",
                )

        return await self.movement_repo.insert(
            user_id=user_id,
            payload=payload,
            performed_by_user_id=user_id,
        )

    async def list_movements(
        self,
        user_id: str,
        filters: StockMovementFilters,
        limit: int,
        offset: int,
    ) -> StockMovementListResponse:
        await self.company_service.require_company(user_id, filters.company_id)
        total_count = await self.movement_repo.count_by_filters(user_id, filters)
        movements = await self.movement_repo.list_by_filters(user_id, filters, limit, offset)
        movement_rows = [StockMovementResponse.model_validate(movement) for movement in movements]
        return StockMovementListResponse(
            **page_response(total_count=total_count, offset=offset, limit=limit, rows=movement_rows),
            movements=movement_rows,
        )

    # --- Stock levels ---

    async def get_stock_levels(self, user_id: str, filters: StockLevelFilters) -> StockLevelListResponse:
        await self.company_service.require_company(user_id, filters.company_id)
        raw_levels, total_count, unique_item_count = await self.movement_repo.aggregate_levels_by_location(
            user_id=user_id,
            filters=filters,
        )
        if not raw_levels:
            return StockLevelListResponse(
                total_stock_level_count=total_count,
                unique_item_count=unique_item_count,
                returned_count=0,
                offset=filters.offset,
                limit=filters.limit,
                truncated=False,
                next_offset=None,
                levels=[],
            )

        item_ids = list({str(level["item_id"]) for level in raw_levels})
        location_ids = list({str(level["location_id"]) for level in raw_levels})

        items_map = await self._load_items_map(user_id, filters.company_id, item_ids)
        locations_map = await self._load_locations_map(user_id, filters.company_id, location_ids)

        levels: list[StockLevel] = []
        for raw in raw_levels:
            level = self._build_stock_level(raw, items_map, locations_map, filters.below_reorder_point)
            if level is not None:
                levels.append(level)

        metadata = page_response(total_count=total_count, offset=filters.offset, limit=filters.limit, rows=levels)
        return StockLevelListResponse(
            total_stock_level_count=total_count,
            unique_item_count=unique_item_count,
            returned_count=metadata["returned_count"],
            offset=metadata["offset"],
            limit=metadata["limit"],
            truncated=metadata["truncated"],
            next_offset=metadata["next_offset"],
            levels=levels,
        )

    async def check_stock_availability(
        self,
        user_id: str,
        company_id: str,
        item_id: str,
        required_quantity: Decimal,
    ) -> Decimal:
        _ = required_quantity
        quantities = await self.movement_repo.aggregate_available_quantities(user_id, company_id, [item_id])
        return quantities.get(item_id, Decimal("0"))

    # --- Invoice integration ---

    async def issue_for_invoice(
        self,
        user_id: str,
        invoice_id: str,
        company_id: str,
        lines: list[dict[str, Any]],
    ) -> list[StockMovementInDB]:
        await self.company_service.require_company(user_id, company_id)

        movements: list[StockMovementInDB] = []
        for line_index, line in enumerate(lines):
            movement = await self._issue_line_for_invoice(
                user_id=user_id,
                invoice_id=invoice_id,
                company_id=company_id,
                line=line,
                line_index=line_index,
            )
            if movement is not None:
                movements.append(movement)

        return movements

    @staticmethod
    def _coerce_stock_quantity(line: dict[str, Any]) -> Decimal:
        quantity = line.get("stock_quantity")
        if quantity is None:
            quantity = line.get("quantity", Decimal("0"))
        if isinstance(quantity, Decimal):
            return abs(quantity)
        return abs(Decimal(str(quantity)))

    async def _load_items_map(
        self,
        user_id: str,
        company_id: str,
        item_ids: list[str],
    ) -> dict[str, InventoryItemInDB]:
        return await self.item_repo.get_many_by_ids(user_id, company_id, item_ids)

    async def _load_locations_map(
        self,
        user_id: str,
        company_id: str,
        location_ids: list[str],
    ) -> dict[str, InventoryLocationInDB]:
        return await self.location_repo.get_many_by_ids(user_id, company_id, location_ids)

    @staticmethod
    def _build_stock_level(
        raw: dict[str, Any],
        items_map: dict[str, InventoryItemInDB],
        locations_map: dict[str, InventoryLocationInDB],
        below_reorder_point: bool,
    ) -> StockLevel | None:
        item_id = str(raw["item_id"])
        location_id = str(raw["location_id"])
        item = items_map.get(item_id)
        location = locations_map.get(location_id)
        if item is None or location is None:
            return None

        quantity = raw["available_quantity"]
        if not isinstance(quantity, Decimal):
            quantity = Decimal(str(quantity))

        if below_reorder_point and item.reorder_point is not None and quantity > item.reorder_point:
            return None

        return StockLevel(
            item_id=item_id,
            item_name=item.name,
            item_sku=item.sku,
            location_id=location_id,
            location_name=location.name,
            available_quantity=quantity,
            unit=item.unit,
        )

    async def _issue_line_for_invoice(
        self,
        user_id: str,
        invoice_id: str,
        company_id: str,
        line: dict[str, Any],
        line_index: int,
    ) -> StockMovementInDB | None:
        item_id_raw = line.get("inventory_item_id")
        if not item_id_raw:
            return None
        item_id = str(item_id_raw)

        stock_quantity = self._coerce_stock_quantity(line)
        if stock_quantity <= Decimal("0"):
            return None

        location_id = await self._resolve_location_id(user_id, company_id, line)
        await self.require_item_for_company(
            user_id=user_id,
            company_id=company_id,
            item_id=item_id,
            location_id=location_id,
        )
        await self._ensure_stock_available(user_id, company_id, item_id, stock_quantity)

        already_exists = await self.movement_repo.has_source_movement(
            user_id=user_id,
            source_type="invoice",
            source_id=invoice_id,
            source_line_id=str(line_index),
        )
        if already_exists:
            return None

        payload = StockMovementCreate.issue_from_invoice(
            company_id=company_id,
            invoice_id=invoice_id,
            item_id=item_id,
            location_id=location_id,
            quantity=stock_quantity,
            line_index=line_index,
        )
        return await self.movement_repo.insert(
            user_id=user_id,
            payload=payload,
            performed_by_user_id=user_id,
        )

    async def _resolve_location_id(self, user_id: str, company_id: str, line: dict[str, Any]) -> str:
        location_id_raw = line.get("inventory_location_id")
        if location_id_raw:
            return str(location_id_raw)
        default_location = await self.get_or_create_default_location(user_id, company_id)
        return default_location.id

    async def _ensure_stock_available(
        self,
        user_id: str,
        company_id: str,
        item_id: str,
        stock_quantity: Decimal,
    ) -> None:
        available = await self.check_stock_availability(
            user_id=user_id,
            company_id=company_id,
            item_id=item_id,
            required_quantity=stock_quantity,
        )
        if available >= stock_quantity:
            return

        item = await self.item_repo.get_by_id(user_id, company_id, item_id)
        item_name = item.name if item else item_id
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient stock for '{item_name}': available {available}, required {stock_quantity}",
        )
