from __future__ import annotations

from datetime import UTC, datetime

from app.models.document_intake import ReceiptExpenseReviewResponse
from app.services.document_workflows.base import (
    DocumentIntakeContext,
    DocumentWorkflowValidationError,
)


class ReceiptDocumentWorkflow:
    async def create_review(self, context: DocumentIntakeContext) -> ReceiptExpenseReviewResponse:
        extraction = context.extraction
        if extraction.document is None or extraction.draft is None:
            raise DocumentWorkflowValidationError(
                "Receipt extraction did not produce an expense draft"
            )

        return ReceiptExpenseReviewResponse(
            classification=extraction.classification,
            document=extraction.document,
            draft=extraction.draft,
            extracted_text=extraction.extracted_text,
            provider=extraction.provider or "unknown",
            model=extraction.model or "unknown",
            extracted_at=extraction.extracted_at or datetime.now(UTC),
        )
