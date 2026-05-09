from __future__ import annotations

import json
from decimal import Decimal
from typing import Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from app.clients.business import BusinessClientError
from app.models.inventory import (
    InventorySearchRequest,
    MovementType,
    ResolveInventoryItemRequest,
)
from app.runtime.tool_context import ToolContext
from app.tools.financial.company_scope import _with_scoped_company

_UNASSIGNED_COMPANY_DESCRIPTION = "Required when the agent is not assigned to one company."


def _json(data: object) -> str:
    return json.dumps(data, default=str, ensure_ascii=False)


def _normalize_guard_query(value: str) -> str:
    return " ".join(value.casefold().split())


class SearchInventoryStockArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )
    query: str = Field(
        max_length=500,
        description="Natural-language item query, for example 'iphones' or 'SKU-001'.",
    )
    include_stock: bool = Field(
        default=True,
        description="Include aggregated stock quantities per match.",
    )
    limit: int = Field(default=20, ge=1, le=100)


class GetStockLevelsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )
    item_id: str | None = Field(
        default=None,
        max_length=64,
        description="Filter to one inventory item.",
    )
    location_id: str | None = Field(
        default=None,
        max_length=64,
        description="Filter to one location.",
    )
    below_reorder_point: bool = Field(
        default=False,
        description="Only return items below reorder point.",
    )
    min_available_quantity: Decimal | None = Field(
        default=None,
        ge=0,
        description="Only return stock levels with available quantity greater than or equal to this value.",
    )
    max_available_quantity: Decimal | None = Field(
        default=None,
        ge=0,
        description="Only return stock levels with available quantity less than or equal to this value.",
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=100,
        description=(
            "Maximum number of matching stock rows to return. unique_item_count and "
            "total_stock_level_count still report all matches."
        ),
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Pagination offset for stock level rows.",
    )
    sort_direction: str = Field(
        default="desc",
        pattern="^(asc|desc)$",
        description="Sort stock levels by available quantity: 'desc' or 'asc'.",
    )


class ListLowStockItemsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )


class ListInventoryItemsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )
    category: str | None = Field(default=None, max_length=120, description="Exact category filter.")
    sku: str | None = Field(default=None, max_length=64, description="Exact SKU filter.")
    barcode: str | None = Field(default=None, max_length=128, description="Exact barcode filter.")
    is_active: bool | None = Field(default=None, description="Filter active/inactive items.")
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ListInventoryCategoriesArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )


class GetStockMovementsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )
    item_id: str | None = Field(default=None, max_length=64)
    location_id: str | None = Field(default=None, max_length=64)
    movement_type: MovementType | None = Field(
        default=None,
        description="Filter by movement type.",
    )
    limit: int = Field(default=30, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ListInventoryLocationsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class GetInventoryOverviewArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )


class GetReorderReportArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ListStockByCategoryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ListNegativeStockItemsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class GetInventoryItemDetailsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )
    item_id: str = Field(min_length=1, max_length=64)
    recent_movements_limit: int = Field(default=20, ge=1, le=100)


class GetInventoryMovementSummaryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )
    group_by: Literal["day", "item", "movement_type"] = "day"
    limit: int = Field(default=30, ge=1, le=100)


class ResolveInventoryItemArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )
    query: str = Field(
        min_length=1,
        max_length=500,
        description="Exact SKU, barcode, alias, or short identifier to resolve before write actions.",
    )
    limit: int = Field(default=5, ge=1, le=20)


def build_inventory_read_tools(
    user_id: str,
    company_id: str | None,
    context: ToolContext,
    repeated_search_queries: set[str] | None = None,
) -> list[StructuredTool]:
    seen_search_queries = repeated_search_queries if repeated_search_queries is not None else set()

    async def search_inventory_stock(**kwargs) -> str:
        args = SearchInventoryStockArgs.model_validate(kwargs)
        normalized_query = args.query.strip()
        if not normalized_query:
            return (
                "search_inventory_stock requires a non-empty query (item name, SKU, or barcode). "
                "For requests like 'items with more than 45 pcs', use get_stock_levels with "
                "min_available_quantity."
            )

        guard_query = _normalize_guard_query(normalized_query)
        if guard_query in seen_search_queries:
            return (
                "This search query was already used in this turn. Do not repeat the same or near-identical "
                "search_inventory_stock call. Use list_inventory_items/get_stock_levels for structured filters "
                "or ask the user for SKU/barcode to resolve the item."
            )
        seen_search_queries.add(guard_query)

        async def run(target_company_id: str) -> str:
            try:
                result = await context.business_client.search_inventory(
                    user_id,
                    InventorySearchRequest(
                        company_id=target_company_id,
                        query=normalized_query,
                        include_stock=args.include_stock,
                        limit=args.limit,
                    ),
                )
            except BusinessClientError as exc:
                return exc.message
            return _json(result.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "searching inventory", run)

    async def resolve_inventory_item(**kwargs) -> str:
        args = ResolveInventoryItemArgs.model_validate(kwargs)
        normalized_query = args.query.strip()
        if not normalized_query:
            return "resolve_inventory_item requires a non-empty SKU, barcode, alias, or identifier query."

        async def run(target_company_id: str) -> str:
            try:
                result = await context.business_client.resolve_inventory_item(
                    user_id,
                    ResolveInventoryItemRequest(
                        company_id=target_company_id,
                        query=normalized_query,
                        limit=args.limit,
                    ),
                )
            except BusinessClientError as exc:
                return exc.message
            return _json(result.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "resolving inventory item", run)

    async def list_inventory_items(**kwargs) -> str:
        args = ListInventoryItemsArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            try:
                result = await context.business_client.list_inventory_items(
                    user_id,
                    company_id=target_company_id,
                    category=args.category,
                    sku=args.sku,
                    barcode=args.barcode,
                    is_active=args.is_active,
                    limit=args.limit,
                    offset=args.offset,
                )
            except BusinessClientError as exc:
                return exc.message
            return _json(result.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "listing inventory items", run)

    async def list_inventory_categories(**kwargs) -> str:
        args = ListInventoryCategoriesArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            try:
                result = await context.business_client.list_inventory_categories(
                    user_id,
                    company_id=target_company_id,
                )
            except BusinessClientError as exc:
                return exc.message
            return _json(result.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "listing inventory categories", run)

    async def get_stock_levels(**kwargs) -> str:
        args = GetStockLevelsArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            try:
                levels = await context.business_client.get_stock_levels(
                    user_id,
                    company_id=target_company_id,
                    item_id=args.item_id,
                    location_id=args.location_id,
                    below_reorder_point=args.below_reorder_point,
                    min_available_quantity=args.min_available_quantity,
                    max_available_quantity=args.max_available_quantity,
                    limit=args.limit,
                    offset=args.offset,
                    sort_direction=args.sort_direction,
                )
            except BusinessClientError as exc:
                return exc.message
            return _json(levels.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "checking stock levels", run)

    async def list_low_stock_items(**kwargs) -> str:
        args = ListLowStockItemsArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            try:
                levels = await context.business_client.get_stock_levels(
                    user_id,
                    company_id=target_company_id,
                    below_reorder_point=True,
                )
            except BusinessClientError as exc:
                return exc.message
            if not levels.levels:
                return "No items are currently below their reorder point."
            return _json(levels.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "listing low-stock items", run)

    async def get_stock_movements(**kwargs) -> str:
        args = GetStockMovementsArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            try:
                result = await context.business_client.list_stock_movements(
                    user_id,
                    company_id=target_company_id,
                    item_id=args.item_id,
                    location_id=args.location_id,
                    movement_type=args.movement_type,
                    limit=args.limit,
                    offset=args.offset,
                )
            except BusinessClientError as exc:
                return exc.message
            return _json(result.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "listing stock movements", run)

    async def list_inventory_locations(**kwargs) -> str:
        args = ListInventoryLocationsArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            try:
                result = await context.business_client.list_inventory_locations(
                    user_id,
                    company_id=target_company_id,
                    limit=args.limit,
                    offset=args.offset,
                )
            except BusinessClientError as exc:
                return exc.message
            return _json(result.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "listing inventory locations", run)

    async def get_inventory_overview(**kwargs) -> str:
        args = GetInventoryOverviewArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            try:
                result = await context.business_client.get_inventory_overview(
                    user_id,
                    company_id=target_company_id,
                )
            except BusinessClientError as exc:
                return exc.message
            return _json(result.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "summarizing inventory", run)

    async def get_reorder_report(**kwargs) -> str:
        args = GetReorderReportArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            try:
                result = await context.business_client.get_reorder_report(
                    user_id,
                    company_id=target_company_id,
                    limit=args.limit,
                    offset=args.offset,
                )
            except BusinessClientError as exc:
                return exc.message
            return _json(result.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "building reorder report", run)

    async def list_stock_by_category(**kwargs) -> str:
        args = ListStockByCategoryArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            try:
                result = await context.business_client.list_stock_by_category(
                    user_id,
                    company_id=target_company_id,
                    limit=args.limit,
                    offset=args.offset,
                )
            except BusinessClientError as exc:
                return exc.message
            return _json(result.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "summarizing stock by category", run)

    async def list_negative_stock_items(**kwargs) -> str:
        args = ListNegativeStockItemsArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            try:
                result = await context.business_client.list_negative_stock_items(
                    user_id,
                    company_id=target_company_id,
                    limit=args.limit,
                    offset=args.offset,
                )
            except BusinessClientError as exc:
                return exc.message
            return _json(result.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "listing negative stock", run)

    async def get_inventory_item_details(**kwargs) -> str:
        args = GetInventoryItemDetailsArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            try:
                result = await context.business_client.get_inventory_item_details(
                    user_id,
                    company_id=target_company_id,
                    item_id=args.item_id,
                    recent_movements_limit=args.recent_movements_limit,
                )
            except BusinessClientError as exc:
                return exc.message
            return _json(result.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "loading item details", run)

    async def get_inventory_movement_summary(**kwargs) -> str:
        args = GetInventoryMovementSummaryArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            try:
                result = await context.business_client.get_inventory_movement_summary(
                    user_id,
                    company_id=target_company_id,
                    group_by=args.group_by,
                    limit=args.limit,
                )
            except BusinessClientError as exc:
                return exc.message
            return _json(result.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "summarizing stock movements", run)

    return [
        StructuredTool.from_function(
            coroutine=get_inventory_overview,
            name="get_inventory_overview",
            description=(
                "Get inventory dashboard totals including item counts, category/location counts, "
                "low-stock count, and negative-stock count."
            ),
            args_schema=GetInventoryOverviewArgs,
        ),
        StructuredTool.from_function(
            coroutine=get_reorder_report,
            name="get_reorder_report",
            description="List item/location rows that are at or below reorder point.",
            args_schema=GetReorderReportArgs,
        ),
        StructuredTool.from_function(
            coroutine=list_stock_by_category,
            name="list_stock_by_category",
            description="Summarize total available stock and item counts grouped by category.",
            args_schema=ListStockByCategoryArgs,
        ),
        StructuredTool.from_function(
            coroutine=list_negative_stock_items,
            name="list_negative_stock_items",
            description="List stock levels that are currently negative.",
            args_schema=ListNegativeStockItemsArgs,
        ),
        StructuredTool.from_function(
            coroutine=get_inventory_item_details,
            name="get_inventory_item_details",
            description="Get one item with stock-by-location and recent movement history.",
            args_schema=GetInventoryItemDetailsArgs,
        ),
        StructuredTool.from_function(
            coroutine=get_inventory_movement_summary,
            name="get_inventory_movement_summary",
            description="Summarize stock movements by day, item, or movement type.",
            args_schema=GetInventoryMovementSummaryArgs,
        ),
        StructuredTool.from_function(
            coroutine=search_inventory_stock,
            name="search_inventory_stock",
            description=(
                "Broad free-text inventory search by item name, SKU, barcode, or alias with optional "
                "aggregated stock totals. Use this for natural-language lookup; do not repeat the same "
                "query in one turn and do not use it to resolve a definitive item before writes."
            ),
            args_schema=SearchInventoryStockArgs,
        ),
        StructuredTool.from_function(
            coroutine=resolve_inventory_item,
            name="resolve_inventory_item",
            description=(
                "Resolve one inventory item for write workflows using exact identifiers first "
                "(SKU/barcode/alias), then ranked candidates if ambiguous."
            ),
            args_schema=ResolveInventoryItemArgs,
        ),
        StructuredTool.from_function(
            coroutine=list_inventory_categories,
            name="list_inventory_categories",
            description=(
                "List normalized inventory categories with item_count and active_item_count facet totals. "
                "Use this for category lists and category-count questions."
            ),
            args_schema=ListInventoryCategoriesArgs,
        ),
        StructuredTool.from_function(
            coroutine=list_inventory_items,
            name="list_inventory_items",
            description=(
                "List inventory item records with optional exact filters: category, SKU, barcode, "
                "or active status. Do not use this for free-text item searches; use "
                "search_inventory_stock when the user provides an item name or natural-language query."
            ),
            args_schema=ListInventoryItemsArgs,
        ),
        StructuredTool.from_function(
            coroutine=get_stock_levels,
            name="get_stock_levels",
            description=(
                "Get current stock levels per item and location. Supports optional quantity filters "
                "for threshold questions and returns total_count plus a capped list of matching rows."
            ),
            args_schema=GetStockLevelsArgs,
        ),
        StructuredTool.from_function(
            coroutine=list_low_stock_items,
            name="list_low_stock_items",
            description="List all items currently below their configured reorder point.",
            args_schema=ListLowStockItemsArgs,
        ),
        StructuredTool.from_function(
            coroutine=get_stock_movements,
            name="get_stock_movements",
            description="List stock movement history with optional item, location, and type filters.",
            args_schema=GetStockMovementsArgs,
        ),
        StructuredTool.from_function(
            coroutine=list_inventory_locations,
            name="list_inventory_locations",
            description="List inventory storage locations for the current company.",
            args_schema=ListInventoryLocationsArgs,
        ),
    ]
