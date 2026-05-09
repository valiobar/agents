from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_inventory_import_service, get_user_id
from app.inventory.models import (
    ImportPreviewStatus,
    InventoryImportPreviewCreate,
    InventoryImportPreviewListResponse,
    InventoryImportPreviewResponse,
    InventoryImportPreviewUpdate,
    InventoryImportResult,
)
from app.inventory.services.inventory_import_service import InventoryImportService

router = APIRouter(prefix="/inventory/import-previews", tags=["inventory-import"])


@router.post("", response_model=InventoryImportPreviewResponse, status_code=status.HTTP_201_CREATED)
async def create_import_preview(
    payload: InventoryImportPreviewCreate,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryImportService, Depends(get_inventory_import_service)],
):
    preview = await service.create_preview(user_id, payload)
    return InventoryImportPreviewResponse.model_validate(preview)


@router.get("", response_model=InventoryImportPreviewListResponse)
async def list_import_previews(
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryImportService, Depends(get_inventory_import_service)],
    company_id: Annotated[str, Query(min_length=1)],
    preview_status: ImportPreviewStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return await service.list_previews(user_id, company_id, preview_status, limit, offset)


@router.get("/{preview_id}", response_model=InventoryImportPreviewResponse)
async def get_import_preview(
    preview_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryImportService, Depends(get_inventory_import_service)],
):
    preview = await service.get_preview(user_id, preview_id)
    return InventoryImportPreviewResponse.model_validate(preview)


@router.patch("/{preview_id}", response_model=InventoryImportPreviewResponse)
async def update_import_preview(
    preview_id: str,
    payload: InventoryImportPreviewUpdate,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryImportService, Depends(get_inventory_import_service)],
):
    preview = await service.update_preview_lines(user_id, preview_id, payload)
    return InventoryImportPreviewResponse.model_validate(preview)


@router.post("/{preview_id}/confirm", response_model=InventoryImportResult)
async def confirm_import_preview(
    preview_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryImportService, Depends(get_inventory_import_service)],
):
    return await service.confirm_preview(user_id, preview_id)


@router.post("/{preview_id}/cancel", response_model=InventoryImportPreviewResponse)
async def cancel_import_preview(
    preview_id: str,
    user_id: Annotated[str, Depends(get_user_id)],
    service: Annotated[InventoryImportService, Depends(get_inventory_import_service)],
):
    preview = await service.cancel_preview(user_id, preview_id)
    return InventoryImportPreviewResponse.model_validate(preview)
