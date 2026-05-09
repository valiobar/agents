from __future__ import annotations

from fastapi import HTTPException, status

from app.company.services.company_service import CompanyService
from app.inventory.models import (
    ImportPreviewStatus,
    InventoryImportPreviewListResponse,
    InventoryImportPreviewCreate,
    InventoryImportPreviewInDB,
    InventoryImportPreviewLine,
    InventoryImportPreviewResponse,
    InventoryImportPreviewUpdate,
    InventoryImportResult,
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryLocationCreate,
    StockMovementCreate,
    SupplierInvoiceLineCandidate,
    page_response,
)
from app.inventory.repositories.inventory_import_preview_repo import InventoryImportPreviewRepository
from app.inventory.repositories.inventory_item_repo import InventoryItemRepository
from app.inventory.repositories.inventory_location_repo import InventoryLocationRepository
from app.inventory.repositories.stock_movement_repo import StockMovementRepository

_IMPORT_PREVIEW_NOT_FOUND = "Import preview not found"
_DRAFT_ONLY_CONFIRM_ERROR = "Only draft previews can be confirmed"
_DRAFT_ONLY_CANCEL_ERROR = "Only draft previews can be cancelled"
_DRAFT_ONLY_UPDATE_ERROR = "Only draft previews can be updated"


class InventoryImportService:
    def __init__(
        self,
        preview_repo: InventoryImportPreviewRepository,
        item_repo: InventoryItemRepository,
        location_repo: InventoryLocationRepository,
        movement_repo: StockMovementRepository,
        company_service: CompanyService,
    ) -> None:
        self.preview_repo = preview_repo
        self.item_repo = item_repo
        self.location_repo = location_repo
        self.movement_repo = movement_repo
        self.company_service = company_service

    @staticmethod
    def _build_preview_line(
        candidate: SupplierInvoiceLineCandidate,
        matched_item_id: str | None,
        default_location_id: str,
    ) -> InventoryImportPreviewLine:
        warnings: list[str] = []
        proposed_item: InventoryItemCreate | None = None

        if not matched_item_id:
            if not candidate.sku:
                warnings.append(
                    "No SKU provided. Set a SKU in the preview before confirming new item creation."
                )
            else:
                proposed_item = InventoryItemCreate(
                    company_id="",  # Filled at confirmation time.
                    sku=candidate.sku,
                    name=candidate.description,
                    unit=candidate.unit or "pcs",
                    selling_price=candidate.unit_price,
                )

        return InventoryImportPreviewLine(
            candidate=candidate,
            matched_item_id=matched_item_id,
            proposed_item=proposed_item,
            location_id=default_location_id,
            receipt_quantity=candidate.quantity,
            warnings=warnings,
        )

    async def create_preview(
        self,
        user_id: str,
        payload: InventoryImportPreviewCreate,
    ) -> InventoryImportPreviewInDB:
        await self.company_service.require_company(user_id, payload.company_id)

        default_location = await self.location_repo.get_default(user_id, payload.company_id)
        if default_location is None:
            default_location = await self.location_repo.create(
                user_id,
                InventoryLocationCreate(
                    company_id=payload.company_id,
                    name="Default",
                    is_default=True,
                ),
            )

        lines: list[InventoryImportPreviewLine] = []
        for candidate in payload.lines:
            match = await self.item_repo.find_best_match(
                user_id=user_id,
                company_id=payload.company_id,
                sku=candidate.sku,
                barcode=candidate.barcode,
                description=candidate.description,
            )
            lines.append(
                self._build_preview_line(
                    candidate=candidate,
                    matched_item_id=match.id if match else None,
                    default_location_id=default_location.id,
                )
            )

        return await self.preview_repo.create(
            user_id=user_id,
            company_id=payload.company_id,
            document_id=payload.document_id,
            source_type=payload.source_type,
            lines=lines,
        )

    async def get_preview(self, user_id: str, preview_id: str) -> InventoryImportPreviewInDB:
        preview = await self.preview_repo.get_by_id(user_id, preview_id)
        if preview is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_IMPORT_PREVIEW_NOT_FOUND)
        return preview

    async def update_preview_lines(
        self,
        user_id: str,
        preview_id: str,
        payload: InventoryImportPreviewUpdate,
    ) -> InventoryImportPreviewInDB:
        preview = await self.get_preview(user_id, preview_id)
        if preview.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_DRAFT_ONLY_UPDATE_ERROR,
            )

        if payload.lines is None:
            return preview

        lines = [InventoryImportPreviewLine(**line.model_dump(mode="python")) for line in payload.lines]
        updated = await self.preview_repo.update_lines(user_id, preview_id, lines)
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_IMPORT_PREVIEW_NOT_FOUND)
        return updated

    async def confirm_preview(self, user_id: str, preview_id: str) -> InventoryImportResult:
        preview = await self.get_preview(user_id, preview_id)
        if preview.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_DRAFT_ONLY_CONFIRM_ERROR,
            )

        items_created = 0
        items_updated = 0
        movements_created = 0

        for line_index, line in enumerate(preview.lines):
            line_items_created, line_items_updated, line_movements_created = await self._confirm_preview_line(
                user_id=user_id,
                preview=preview,
                line=line,
                line_index=line_index,
            )
            items_created += line_items_created
            items_updated += line_items_updated
            movements_created += line_movements_created

        confirmed = await self.preview_repo.mark_confirmed(user_id, preview_id)
        if confirmed is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_IMPORT_PREVIEW_NOT_FOUND)

        return InventoryImportResult(
            preview_id=preview_id,
            items_created=items_created,
            items_updated=items_updated,
            movements_created=movements_created,
        )

    async def _confirm_preview_line(
        self,
        user_id: str,
        preview: InventoryImportPreviewInDB,
        line: InventoryImportPreviewLine,
        line_index: int,
    ) -> tuple[int, int, int]:
        item_id, items_created, items_updated = await self._resolve_line_item_id(user_id, preview, line)
        if item_id is None:
            return (items_created, items_updated, 0)

        location_exists = await self.location_repo.exists(
            user_id=user_id,
            company_id=preview.company_id,
            location_id=line.location_id,
        )
        if not location_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inventory location '{line.location_id}' not found in this company",
            )

        already_imported = await self.movement_repo.has_source_movement(
            user_id=user_id,
            source_type="supplier_invoice_import",
            source_id=preview.id,
            source_line_id=str(line_index),
        )
        if already_imported:
            return (items_created, items_updated, 0)

        movement_payload = StockMovementCreate.receipt_from_import(
            preview_id=preview.id,
            company_id=preview.company_id,
            item_id=item_id,
            location_id=line.location_id,
            quantity=line.receipt_quantity,
            line_index=line_index,
        )
        await self.movement_repo.insert(
            user_id=user_id,
            payload=movement_payload,
            performed_by_user_id=user_id,
        )
        return (items_created, items_updated, 1)

    async def _resolve_line_item_id(
        self,
        user_id: str,
        preview: InventoryImportPreviewInDB,
        line: InventoryImportPreviewLine,
    ) -> tuple[str | None, int, int]:
        item_id = line.matched_item_id
        items_created = 0
        items_updated = 0

        if item_id is not None:
            was_updated = await self._fill_missing_selling_price(
                user_id=user_id,
                company_id=preview.company_id,
                item_id=item_id,
                unit_price=line.candidate.unit_price,
            )
            return (item_id, items_created, items_updated + int(was_updated))

        if line.proposed_item is None:
            return (None, items_created, items_updated)

        proposed = InventoryItemCreate(
            **{**line.proposed_item.model_dump(mode="python"), "company_id": preview.company_id}
        )
        existing_item = await self.item_repo.find_by_sku(user_id, preview.company_id, proposed.sku)
        if existing_item:
            was_updated = await self._fill_missing_selling_price(
                user_id=user_id,
                company_id=preview.company_id,
                item_id=existing_item.id,
                unit_price=line.candidate.unit_price,
            )
            return (existing_item.id, items_created, items_updated + int(was_updated))

        new_item = await self.item_repo.create(
            user_id=user_id,
            payload=proposed,
            changed_by_user_id=user_id,
        )
        return (new_item.id, items_created + 1, items_updated)

    async def _fill_missing_selling_price(
        self,
        user_id: str,
        company_id: str,
        item_id: str,
        unit_price,
    ) -> bool:
        if unit_price is None:
            return False

        item = await self.item_repo.get_by_id(user_id, company_id, item_id)
        if item is None or item.selling_price is not None:
            return False

        await self.item_repo.update(
            user_id=user_id,
            company_id=company_id,
            item_id=item_id,
            payload=InventoryItemUpdate(selling_price=unit_price),
            changed_by_user_id=user_id,
        )
        return True

    async def cancel_preview(self, user_id: str, preview_id: str) -> InventoryImportPreviewInDB:
        preview = await self.get_preview(user_id, preview_id)
        if preview.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_DRAFT_ONLY_CANCEL_ERROR,
            )

        cancelled = await self.preview_repo.mark_cancelled(user_id, preview_id)
        if cancelled is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_IMPORT_PREVIEW_NOT_FOUND)
        return cancelled

    async def list_previews(
        self,
        user_id: str,
        company_id: str,
        preview_status: ImportPreviewStatus | None,
        limit: int,
        offset: int,
    ) -> InventoryImportPreviewListResponse:
        await self.company_service.require_company(user_id, company_id)
        total_count = await self.preview_repo.count_by_filters(user_id, company_id, preview_status)
        previews = await self.preview_repo.list_by_company(
            user_id=user_id,
            company_id=company_id,
            status=preview_status,
            limit=limit,
            offset=offset,
        )
        preview_rows = [InventoryImportPreviewResponse.model_validate(preview) for preview in previews]
        return InventoryImportPreviewListResponse(
            **page_response(total_count=total_count, offset=offset, limit=limit, rows=preview_rows),
            previews=preview_rows,
        )
