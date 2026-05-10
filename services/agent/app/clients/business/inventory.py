from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.clients.business.base import _BusinessClientBase
from app.models.inventory import (
    InventoryItemDetailsResponse,
    InventoryMovementSummaryResponse,
    InventoryOverviewResponse,
    InventoryCategoryListResponse,
    InventoryImportPreviewCreate,
    InventoryImportPreviewListResponse,
    InventoryImportPreviewResponse,
    InventoryImportResult,
    InventoryItemCreate,
    InventoryItemListResponse,
    InventoryItemResponse,
    InventoryItemUpdate,
    InventoryLocationListResponse,
    InventoryLocationResponse,
    InventorySearchRequest,
    InventorySearchResponse,
    ResolveInventoryItemRequest,
    ResolveInventoryItemResponse,
    NegativeStockResponse,
    ReorderReportResponse,
    StockLevelListResponse,
    StockByCategoryResponse,
    StockMovementListResponse,
    StockMovementCreate,
    StockMovementResponse,
)


class _InventoryClient(_BusinessClientBase):
    async def get_inventory_overview(
        self,
        user_id: str,
        *,
        company_id: str,
    ) -> InventoryOverviewResponse:
        data = await self._request(
            "GET",
            "/inventory/reports/overview",
            user_id,
            params={"company_id": company_id},
        )
        return InventoryOverviewResponse.model_validate(data)

    async def get_reorder_report(
        self,
        user_id: str,
        *,
        company_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> ReorderReportResponse:
        data = await self._request(
            "GET",
            "/inventory/reports/reorder",
            user_id,
            params={"company_id": company_id, "limit": limit, "offset": offset},
        )
        return ReorderReportResponse.model_validate(data)

    async def list_stock_by_category(
        self,
        user_id: str,
        *,
        company_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> StockByCategoryResponse:
        data = await self._request(
            "GET",
            "/inventory/reports/stock-by-category",
            user_id,
            params={"company_id": company_id, "limit": limit, "offset": offset},
        )
        return StockByCategoryResponse.model_validate(data)

    async def list_negative_stock_items(
        self,
        user_id: str,
        *,
        company_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> NegativeStockResponse:
        data = await self._request(
            "GET",
            "/inventory/reports/negative-stock",
            user_id,
            params={"company_id": company_id, "limit": limit, "offset": offset},
        )
        return NegativeStockResponse.model_validate(data)

    async def get_inventory_item_details(
        self,
        user_id: str,
        *,
        company_id: str,
        item_id: str,
        recent_movements_limit: int = 20,
    ) -> InventoryItemDetailsResponse:
        data = await self._request(
            "GET",
            f"/inventory/items/{item_id}/details",
            user_id,
            params={"company_id": company_id, "recent_movements_limit": recent_movements_limit},
        )
        return InventoryItemDetailsResponse.model_validate(data)

    async def get_inventory_movement_summary(
        self,
        user_id: str,
        *,
        company_id: str,
        group_by: str = "day",
        limit: int = 30,
    ) -> InventoryMovementSummaryResponse:
        data = await self._request(
            "GET",
            "/inventory/reports/movement-summary",
            user_id,
            params={"company_id": company_id, "group_by": group_by, "limit": limit},
        )
        return InventoryMovementSummaryResponse.model_validate(data)

    async def list_inventory_categories(
        self,
        user_id: str,
        *,
        company_id: str,
    ) -> InventoryCategoryListResponse:
        data = await self._request(
            "GET",
            "/inventory/categories",
            user_id,
            params={"company_id": company_id},
        )
        return InventoryCategoryListResponse.model_validate(data)

    async def list_inventory_items(
        self,
        user_id: str,
        *,
        company_id: str,
        category: str | None = None,
        is_active: bool | None = None,
        sku: str | None = None,
        barcode: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> InventoryItemListResponse:
        params: dict[str, Any] = {"company_id": company_id, "limit": limit, "offset": offset}
        if category is not None:
            params["category"] = category
        if is_active is not None:
            params["is_active"] = is_active
        if sku is not None:
            params["sku"] = sku
        if barcode is not None:
            params["barcode"] = barcode

        data = await self._request("GET", "/inventory/items", user_id, params=params)
        return InventoryItemListResponse.model_validate(data)

    async def get_inventory_item(
        self,
        user_id: str,
        *,
        company_id: str,
        item_id: str,
    ) -> InventoryItemResponse:
        data = await self._request(
            "GET",
            f"/inventory/items/{item_id}",
            user_id,
            params={"company_id": company_id},
        )
        return InventoryItemResponse.model_validate(data)

    async def create_inventory_item(
        self,
        user_id: str,
        payload: InventoryItemCreate,
    ) -> InventoryItemResponse:
        data = await self._request(
            "POST",
            "/inventory/items",
            user_id,
            json=payload.model_dump(mode="json"),
        )
        return InventoryItemResponse.model_validate(data)

    async def update_inventory_item(
        self,
        user_id: str,
        *,
        company_id: str,
        item_id: str,
        payload: InventoryItemUpdate,
    ) -> InventoryItemResponse:
        data = await self._request(
            "PATCH",
            f"/inventory/items/{item_id}",
            user_id,
            params={"company_id": company_id},
            json=payload.model_dump(mode="json", exclude_none=True),
        )
        return InventoryItemResponse.model_validate(data)

    async def list_inventory_locations(
        self,
        user_id: str,
        *,
        company_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> InventoryLocationListResponse:
        data = await self._request(
            "GET",
            "/inventory/locations",
            user_id,
            params={"company_id": company_id, "limit": limit, "offset": offset},
        )
        return InventoryLocationListResponse.model_validate(data)

    async def create_stock_movement(
        self,
        user_id: str,
        payload: StockMovementCreate,
    ) -> StockMovementResponse:
        data = await self._request(
            "POST",
            "/inventory/movements",
            user_id,
            json=payload.model_dump(mode="json"),
        )
        return StockMovementResponse.model_validate(data)

    async def list_stock_movements(
        self,
        user_id: str,
        *,
        company_id: str,
        item_id: str | None = None,
        location_id: str | None = None,
        movement_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> StockMovementListResponse:
        params: dict[str, Any] = {"company_id": company_id, "limit": limit, "offset": offset}
        if item_id is not None:
            params["item_id"] = item_id
        if location_id is not None:
            params["location_id"] = location_id
        if movement_type is not None:
            params["movement_type"] = movement_type

        data = await self._request("GET", "/inventory/movements", user_id, params=params)
        return StockMovementListResponse.model_validate(data)

    async def get_stock_levels(
        self,
        user_id: str,
        *,
        company_id: str,
        item_id: str | None = None,
        location_id: str | None = None,
        below_reorder_point: bool = False,
        min_available_quantity: Decimal | None = None,
        max_available_quantity: Decimal | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_direction: str = "desc",
    ) -> StockLevelListResponse:
        params: dict[str, Any] = {
            "company_id": company_id,
            "below_reorder_point": below_reorder_point,
            "limit": limit,
            "offset": offset,
            "sort_direction": sort_direction,
        }
        if item_id is not None:
            params["item_id"] = item_id
        if location_id is not None:
            params["location_id"] = location_id
        if min_available_quantity is not None:
            params["min_available_quantity"] = min_available_quantity
        if max_available_quantity is not None:
            params["max_available_quantity"] = max_available_quantity

        data = await self._request("GET", "/inventory/levels", user_id, params=params)
        return StockLevelListResponse.model_validate(data)

    async def search_inventory(
        self,
        user_id: str,
        payload: InventorySearchRequest,
    ) -> InventorySearchResponse:
        data = await self._request(
            "POST",
            "/inventory/search",
            user_id,
            json=payload.model_dump(mode="json"),
        )
        return InventorySearchResponse.model_validate(data)

    async def resolve_inventory_item(
        self,
        user_id: str,
        payload: ResolveInventoryItemRequest,
    ) -> ResolveInventoryItemResponse:
        data = await self._request(
            "POST",
            "/inventory/resolve-item",
            user_id,
            json=payload.model_dump(mode="json"),
        )
        return ResolveInventoryItemResponse.model_validate(data)

    async def create_import_preview(
        self,
        user_id: str,
        payload: InventoryImportPreviewCreate,
    ) -> InventoryImportPreviewResponse:
        data = await self._request(
            "POST",
            "/inventory/import-previews",
            user_id,
            json=payload.model_dump(mode="json"),
        )
        return InventoryImportPreviewResponse.model_validate(data)

    async def list_import_previews(
        self,
        user_id: str,
        *,
        company_id: str,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> InventoryImportPreviewListResponse:
        params: dict[str, Any] = {"company_id": company_id, "limit": limit, "offset": offset}
        if status is not None:
            params["preview_status"] = status

        data = await self._request("GET", "/inventory/import-previews", user_id, params=params)
        return InventoryImportPreviewListResponse.model_validate(data)

    async def get_import_preview(
        self,
        user_id: str,
        *,
        preview_id: str,
    ) -> InventoryImportPreviewResponse:
        data = await self._request("GET", f"/inventory/import-previews/{preview_id}", user_id)
        return InventoryImportPreviewResponse.model_validate(data)

    async def update_import_preview(
        self,
        user_id: str,
        *,
        preview_id: str,
        lines: list[dict[str, Any]],
    ) -> InventoryImportPreviewResponse:
        data = await self._request(
            "PATCH",
            f"/inventory/import-previews/{preview_id}",
            user_id,
            json={"lines": lines},
        )
        return InventoryImportPreviewResponse.model_validate(data)

    async def confirm_import_preview(
        self,
        user_id: str,
        *,
        preview_id: str,
    ) -> InventoryImportResult:
        data = await self._request(
            "POST",
            f"/inventory/import-previews/{preview_id}/confirm",
            user_id,
        )
        return InventoryImportResult.model_validate(data)

    async def cancel_import_preview(
        self,
        user_id: str,
        *,
        preview_id: str,
    ) -> InventoryImportPreviewResponse:
        data = await self._request(
            "POST",
            f"/inventory/import-previews/{preview_id}/cancel",
            user_id,
        )
        return InventoryImportPreviewResponse.model_validate(data)
