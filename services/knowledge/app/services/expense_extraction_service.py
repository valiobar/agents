from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from app.models.expense_extraction import ExpenseDraft, ExpenseDraftRequestSourceDocumentType
from app.services.expense_extraction_provider import ExpenseExtractionProvider
from app.services.loaders import load_document


class ExpenseExtractionResult(BaseModel):
    draft: ExpenseDraft
    extracted_text: str | None
    extracted_at: datetime
    provider: str
    model: str


class ExpenseExtractionService:
    def __init__(self, *, provider: ExpenseExtractionProvider, provider_name: str, model: str) -> None:
        self.provider = provider
        self.provider_name = provider_name
        self.model = model

    async def extract(
        self,
        *,
        filename: str,
        content_type: str,
        content: bytes,
        source_document_type: ExpenseDraftRequestSourceDocumentType,
        source_document_id: str,
    ) -> ExpenseExtractionResult:
        extracted_text: str | None = None

        if content_type in {"application/pdf", "text/plain", "text/markdown"}:
            pages = await load_document(content, content_type)
            extracted_text = "\n\n".join(page.text for page in pages).strip() or None

        draft = await self.provider.extract_draft(
            filename=filename,
            content_type=content_type,
            content=content,
            extracted_text=extracted_text,
            source_document_type=source_document_type,
            source_document_id=source_document_id,
        )

        return ExpenseExtractionResult(
            draft=draft,
            extracted_text=extracted_text,
            extracted_at=datetime.now(UTC),
            provider=self.provider_name,
            model=self.model,
        )
