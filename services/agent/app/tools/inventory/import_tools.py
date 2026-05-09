from __future__ import annotations

import json

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from app.clients.business import BusinessClientError
from app.models.inventory import ImportPreviewStatus
from app.runtime.tool_context import ToolContext
from app.tools.financial.company_scope import _with_scoped_company

_UNASSIGNED_COMPANY_DESCRIPTION = "Required when the agent is not assigned to one company."


def _json(data: object) -> str:
    return json.dumps(data, default=str, ensure_ascii=False)


class ListImportPreviewsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str | None = Field(
        default=None,
        max_length=64,
        description=_UNASSIGNED_COMPANY_DESCRIPTION,
    )
    status: ImportPreviewStatus | None = Field(
        default=None,
        description="Filter by status.",
    )
    limit: int = Field(default=20, ge=1, le=100)


class GetImportPreviewArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_id: str = Field(min_length=1, max_length=64)


class ConfirmImportPreviewArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_id: str = Field(min_length=1, max_length=64)
    confirmed: bool = Field(
        default=False,
        description="Must be true only after the user explicitly confirms the import.",
    )


class CancelImportPreviewArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preview_id: str = Field(min_length=1, max_length=64)


def build_inventory_import_tools(
    user_id: str,
    company_id: str | None,
    context: ToolContext,
) -> list[StructuredTool]:
    async def list_import_previews(**kwargs) -> str:
        args = ListImportPreviewsArgs.model_validate(kwargs)

        async def run(target_company_id: str) -> str:
            try:
                result = await context.business_client.list_import_previews(
                    user_id,
                    company_id=target_company_id,
                    status=args.status,
                    limit=args.limit,
                )
            except BusinessClientError as exc:
                return exc.message
            return _json(result.model_dump(mode="json"))

        return await _with_scoped_company(company_id, args.company_id, "listing import previews", run)

    async def get_import_preview(**kwargs) -> str:
        args = GetImportPreviewArgs.model_validate(kwargs)
        try:
            preview = await context.business_client.get_import_preview(user_id, preview_id=args.preview_id)
        except BusinessClientError as exc:
            return exc.message
        return _json(preview.model_dump(mode="json"))

    async def confirm_import_preview(**kwargs) -> str:
        args = ConfirmImportPreviewArgs.model_validate(kwargs)
        if not args.confirmed:
            return _json(
                {
                    "message": (
                        "Confirmation required. Review the import preview with the user and ask "
                        "them to confirm before creating inventory items and receipt movements."
                    ),
                    "preview_id": args.preview_id,
                }
            )
        try:
            result = await context.business_client.confirm_import_preview(user_id, preview_id=args.preview_id)
        except BusinessClientError as exc:
            return exc.message
        return _json(result.model_dump(mode="json"))

    async def cancel_import_preview(**kwargs) -> str:
        args = CancelImportPreviewArgs.model_validate(kwargs)
        try:
            preview = await context.business_client.cancel_import_preview(user_id, preview_id=args.preview_id)
        except BusinessClientError as exc:
            return exc.message
        return _json(preview.model_dump(mode="json"))

    return [
        StructuredTool.from_function(
            coroutine=list_import_previews,
            name="list_import_previews",
            description=(
                "List supplier invoice import previews, optionally filtered by status "
                "(draft/confirmed/cancelled)."
            ),
            args_schema=ListImportPreviewsArgs,
        ),
        StructuredTool.from_function(
            coroutine=get_import_preview,
            name="get_import_preview",
            description="Load one import preview to review extracted lines, matched items, and warnings.",
            args_schema=GetImportPreviewArgs,
        ),
        StructuredTool.from_function(
            coroutine=confirm_import_preview,
            name="confirm_import_preview",
            description=(
                "Confirm a draft import preview to create/update inventory items and receipt movements. "
                "Call with confirmed=false first, then call confirmed=true only after user confirmation."
            ),
            args_schema=ConfirmImportPreviewArgs,
        ),
        StructuredTool.from_function(
            coroutine=cancel_import_preview,
            name="cancel_import_preview",
            description="Cancel a draft import preview. No items or movements are created.",
            args_schema=CancelImportPreviewArgs,
        ),
    ]
