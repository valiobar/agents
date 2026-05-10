from __future__ import annotations

from datetime import UTC, datetime

from app.models.document_intake import (
    SupplierInvoiceExpenseReviewResponse,
    SupplierInvoiceInventoryReviewResponse,
)
from app.models.inventory import InventoryImportPreviewCreate, SupplierInvoiceLineCandidate
from app.services.document_workflows.base import (
    DocumentIntakeContext,
    DocumentWorkflowValidationError,
)


class SupplierInvoiceDocumentWorkflow:
    async def create_review(
        self, context: DocumentIntakeContext
    ) -> SupplierInvoiceExpenseReviewResponse | SupplierInvoiceInventoryReviewResponse:
        extraction = context.extraction
        if extraction.document is None or extraction.draft is None:
            raise DocumentWorkflowValidationError(
                "Supplier invoice extraction did not produce an expense draft"
            )

        if not extraction.draft.items:
            return SupplierInvoiceExpenseReviewResponse(
                classification=extraction.classification,
                document=extraction.document,
                draft=extraction.draft,
                extracted_text=extraction.extracted_text,
                provider=extraction.provider or "unknown",
                model=extraction.model or "unknown",
                extracted_at=extraction.extracted_at or datetime.now(UTC),
            )

        preview = await context.business_client.create_import_preview(
            context.user_id,
            InventoryImportPreviewCreate(
                company_id=context.company_id,
                document_id=extraction.document.id,
                source_type="supplier_invoice_upload",
                lines=[
                    SupplierInvoiceLineCandidate(
                        description=item.description,
                        sku=item.sku,
                        barcode=item.barcode,
                        quantity=item.quantity,
                        unit=item.unit_label,
                        unit_price=item.unit_price,
                    )
                    for item in extraction.draft.items
                ],
            ),
        )
        return SupplierInvoiceInventoryReviewResponse(
            classification=extraction.classification,
            document=extraction.document,
            draft=extraction.draft,
            extracted_text=extraction.extracted_text,
            provider=extraction.provider or "unknown",
            model=extraction.model or "unknown",
            extracted_at=extraction.extracted_at or datetime.now(UTC),
            inventory_import_preview=preview,
        )
