from __future__ import annotations

import json
from decimal import Decimal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from app.clients.business import BusinessClientError
from app.models.inventory import InventoryItemCreate, InventoryItemUpdate, MovementType, StockMovementCreate
from app.runtime.tool_context import ToolContext
from app.tools.financial.company_scope import _with_scoped_company

_UNASSIGNED_COMPANY_DESCRIPTION = "Required when the agent is not assigned to one company."


def _json(data: object) -> str:
    return json.dumps(data, default=str, ensure_ascii=False)


class CreateInventoryItemArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, max_length=120)
    barcode: str | None = Field(default=None, max_length=128)
    aliases: list[str] = Field(default_factory=list)
    unit: str = Field(min_length=1, max_length=32)
    selling_price: Decimal | None = Field(default=None, ge=0)
    reorder_point: Decimal | None = Field(default=None, ge=0)
    target_stock_level: Decimal | None = Field(default=None, ge=0)
    supplier_partner_id: str | None = Field(default=None, max_length=64)
    confirmed: bool = Field(
        default=False,
        description="Must be true only after the user explicitly confirms item creation.",
    )


class UpdateInventoryItemArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )
    item_id: str = Field(min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, max_length=120)
    barcode: str | None = Field(default=None, max_length=128)
    aliases: list[str] | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=32)
    selling_price: Decimal | None = Field(default=None, ge=0)
    reorder_point: Decimal | None = Field(default=None, ge=0)
    target_stock_level: Decimal | None = Field(default=None, ge=0)
    supplier_partner_id: str | None = Field(default=None, max_length=64)
    is_active: bool | None = None
    confirmed: bool = Field(
        default=False,
        description="Must be true only after the user explicitly confirms the update.",
    )


class RecordStockMovementArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )
    item_id: str = Field(min_length=1, max_length=64)
    location_id: str | None = Field(
        default=None,
        max_length=64,
        description="Optional; if omitted, the default inventory location is used.",
    )
    movement_type: MovementType = Field(description="Movement type.")
    quantity_delta: Decimal = Field(description="Positive for receipt, negative for issue.")
    reason: str | None = Field(default=None, max_length=500)
    confirmed: bool = Field(
        default=False,
        description="Must be true only after the user explicitly confirms recording the movement.",
    )


def build_inventory_write_tools(
    user_id: str,
    company_id: str | None,
    context: ToolContext,
) -> list[StructuredTool]:
    async def create_inventory_item(**kwargs) -> str:
        args = CreateInventoryItemArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            payload = InventoryItemCreate(
                company_id=target_company_id,
                sku=args.sku,
                name=args.name,
                description=args.description,
                category=args.category,
                barcode=args.barcode,
                aliases=args.aliases,
                unit=args.unit,
                selling_price=args.selling_price,
                reorder_point=args.reorder_point,
                target_stock_level=args.target_stock_level,
                supplier_partner_id=args.supplier_partner_id,
            )
            if not args.confirmed:
                return _json(
                    {
                        "message": "Confirmation required. Present this item draft and ask the user to confirm.",
                        "item_draft": payload.model_dump(mode="json"),
                    }
                )
            try:
                item = await context.business_client.create_inventory_item(user_id, payload)
            except BusinessClientError as exc:
                return exc.message
            return _json(item.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "creating inventory item", run)

    async def update_inventory_item(**kwargs) -> str:
        args = UpdateInventoryItemArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            update_fields = args.model_dump(exclude={"company_id", "item_id", "confirmed"}, exclude_none=True)
            if not args.confirmed:
                return _json(
                    {
                        "message": "Confirmation required. Present these changes and ask the user to confirm.",
                        "item_id": args.item_id,
                        "updates": update_fields,
                    }
                )
            payload = InventoryItemUpdate.model_validate(update_fields)
            try:
                item = await context.business_client.update_inventory_item(
                    user_id,
                    company_id=target_company_id,
                    item_id=args.item_id,
                    payload=payload,
                )
            except BusinessClientError as exc:
                return exc.message
            return _json(item.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "updating inventory item", run)

    async def record_stock_movement(**kwargs) -> str:
        args = RecordStockMovementArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            resolved_location_id = args.location_id.strip() if args.location_id else None
            if not resolved_location_id:
                try:
                    locations_response = await context.business_client.list_inventory_locations(
                        user_id,
                        company_id=target_company_id,
                        limit=100,
                    )
                except BusinessClientError as exc:
                    return exc.message
                locations = locations_response.locations
                if not locations:
                    return (
                        "No inventory locations found for this company. "
                        "Create a location first, then retry recording the movement."
                    )
                default_location = next((location for location in locations if location.is_default), locations[0])
                resolved_location_id = default_location.id

            payload = StockMovementCreate(
                company_id=target_company_id,
                item_id=args.item_id,
                location_id=resolved_location_id,
                movement_type=args.movement_type,
                quantity_delta=args.quantity_delta,
                reason=args.reason,
            )
            if not args.confirmed:
                return _json(
                    {
                        "message": (
                            "Confirmation required. Present this stock movement and ask the user to confirm."
                        ),
                        "movement_draft": payload.model_dump(mode="json"),
                    }
                )
            try:
                movement = await context.business_client.create_stock_movement(user_id, payload)
            except BusinessClientError as exc:
                return exc.message
            return _json(movement.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "recording stock movement", run)

    return [
        StructuredTool.from_function(
            coroutine=create_inventory_item,
            name="create_inventory_item",
            description=(
                "Create a new inventory item. Call with confirmed=false first to show a draft, "
                "then call confirmed=true only after explicit user confirmation. If the latest "
                "user message is an affirmative reply to your immediately previous draft "
                "(e.g. yes/да/da/ok), call confirmed=true with the same draft values."
            ),
            args_schema=CreateInventoryItemArgs,
        ),
        StructuredTool.from_function(
            coroutine=update_inventory_item,
            name="update_inventory_item",
            description=(
                "Update an existing inventory item. Call with confirmed=false first to show changes, "
                "then call confirmed=true only after explicit user confirmation. If the latest "
                "user message is an affirmative reply to your immediately previous draft "
                "(e.g. yes/да/da/ok), call confirmed=true with the same draft values."
            ),
            args_schema=UpdateInventoryItemArgs,
        ),
        StructuredTool.from_function(
            coroutine=record_stock_movement,
            name="record_stock_movement",
            description=(
                "Record a stock movement (receipt, issue, adjustment, transfer, return). "
                "Call with confirmed=false first to show the draft, then call confirmed=true after user "
                "confirmation. If the latest user message is an affirmative reply to your immediately "
                "previous movement draft (e.g. yes/да/da/ok), call confirmed=true with exactly the same values."
            ),
            args_schema=RecordStockMovementArgs,
        ),
    ]
