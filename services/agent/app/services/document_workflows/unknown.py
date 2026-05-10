from __future__ import annotations

from app.models.document_intake import UnknownDocumentReviewResponse
from app.services.document_workflows.base import DocumentIntakeContext


class UnknownDocumentWorkflow:
    async def create_review(self, context: DocumentIntakeContext) -> UnknownDocumentReviewResponse:
        extraction = context.extraction
        return UnknownDocumentReviewResponse(
            classification=extraction.classification,
            document=extraction.document,
            extracted_text=extraction.extracted_text,
            warnings=list(extraction.classification.warnings),
        )
