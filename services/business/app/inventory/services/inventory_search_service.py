from __future__ import annotations

from decimal import Decimal

from app.company.services.company_service import CompanyService
from app.inventory.models import (
    InventorySearchRequest,
    InventorySearchResponse,
    ResolveInventoryItemRequest,
    ResolveInventoryItemResponse,
)
from app.inventory.repositories.inventory_item_repo import InventoryItemRepository, normalize_text
from app.inventory.repositories.stock_movement_repo import StockMovementRepository


class InventorySearchService:
    def __init__(
        self,
        item_repo: InventoryItemRepository,
        movement_repo: StockMovementRepository,
        company_service: CompanyService,
    ) -> None:
        self.item_repo = item_repo
        self.movement_repo = movement_repo
        self.company_service = company_service

    async def search(self, user_id: str, payload: InventorySearchRequest) -> InventorySearchResponse:
        await self.company_service.require_company(user_id, payload.company_id)
        normalized_query = normalize_text(payload.query)

        matches = await self.item_repo.search_items(
            user_id=user_id,
            company_id=payload.company_id,
            query=payload.query,
            limit=payload.limit,
        )

        if payload.include_stock and matches:
            item_ids = [match.item_id for match in matches]
            quantities = await self.movement_repo.aggregate_available_quantities(
                user_id=user_id,
                company_id=payload.company_id,
                item_ids=item_ids,
            )
            for match in matches:
                match.available_quantity = quantities.get(match.item_id, Decimal("0"))

        filtered_matches = [match for match in matches if match.confidence >= payload.min_confidence]

        total_available_quantity: Decimal | None = None
        if payload.include_stock and filtered_matches:
            total_available_quantity = sum(
                (match.available_quantity or Decimal("0")) for match in filtered_matches
            )

        message: str | None = None
        if not filtered_matches:
            message = (
                "No inventory items matched this query. Do not retry the same or near-identical query; "
                "ask for SKU/barcode or use structured list tools when appropriate."
            )

        return InventorySearchResponse(
            query=payload.query,
            normalized_query=normalized_query,
            matches=filtered_matches,
            total_available_quantity=total_available_quantity,
            message=message,
        )

    async def resolve_item(
        self,
        user_id: str,
        payload: ResolveInventoryItemRequest,
    ) -> ResolveInventoryItemResponse:
        await self.company_service.require_company(user_id, payload.company_id)
        normalized_query = normalize_text(payload.query)

        exact_candidates = await self.item_repo.find_exact_identifier_or_alias(
            user_id=user_id,
            company_id=payload.company_id,
            query=payload.query,
            limit=payload.limit,
        )

        if len(exact_candidates) == 1 and exact_candidates[0].confidence >= 0.95:
            return ResolveInventoryItemResponse(
                query=payload.query,
                normalized_query=normalized_query,
                exact_match=exact_candidates[0],
                candidates=[],
                message=None,
            )

        candidates = exact_candidates
        if not candidates:
            candidates = await self.item_repo.search_items(
                user_id=user_id,
                company_id=payload.company_id,
                query=payload.query,
                limit=payload.limit,
            )

        limited_candidates = candidates[: payload.limit]
        message = (
            "Choose one candidate or ask the user for SKU/barcode."
            if limited_candidates
            else "No inventory item could be resolved. Ask the user for SKU or barcode."
        )
        return ResolveInventoryItemResponse(
            query=payload.query,
            normalized_query=normalized_query,
            exact_match=None,
            candidates=limited_candidates,
            message=message,
        )
